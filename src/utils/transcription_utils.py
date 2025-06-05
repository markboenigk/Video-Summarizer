import json
import logging

import openai

from utils.aws_utils import (
    get_json_from_s3,
    get_video_path_from_s3,
    load_video_file_from_s3,
    save_transcription_to_s3_and_dynamo,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def is_transcribed(record: dict) -> bool:
    """
    Check if the given record has already been transcribed.

    Args:
        record (dict): Record from the database.

    Returns:
        bool: True if transcription is already completed.
    """
    return record.get("is_transcribed", False)


def transcribe_audio(file_path: str, api_key: str) -> dict | None:
    """
    Transcribe audio from a local file using OpenAI Whisper API.

    Args:
        file_path (str): Path to the audio file.
        api_key (str): OpenAI API key.

    Returns:
        dict | None: JSON response from OpenAI or None if an error occurs.
    """
    openai.api_key = api_key
    try:
        with open(file_path, 'rb') as audio_file:
            transcript = openai.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file
            )
            return json.loads(transcript.to_json())
    except Exception as e:
        logger.error(f"Error during transcription: {e}")
        return None


def get_transcription(
    config_dict: dict,
    video_dict: dict,
    record: dict,
    api_key: str
) -> str:
    """
    Fetch or generate a transcription for a video.

    Args:
        config_dict (dict): Configuration with S3 and DynamoDB info.
        video_dict (dict): Optional video path dictionary (preloaded).
        record (dict): Record associated with the video.
        api_key (str): OpenAI API key.

    Returns:
        str: Transcription text, potentially with caption appended.
    """
    transcribed_record = record if record and is_transcribed(record) else None

    if transcribed_record is None:
        logger.info("Video hasn't been transcribed yet")

        if video_dict and 'video_path' in video_dict:
            transcription = transcribe_audio(video_dict['video_path'], api_key)
        else:
            logger.info("Loading video file from S3 for transcription")
            video_path_s3 = get_video_path_from_s3(
                config_dict['dynamo_table'],
                config_dict['chat_id'],
                config_dict['videocode']
            )
            local_path = load_video_file_from_s3(
                config_dict['bucket_name'],
                file_key=video_path_s3
            )
            transcription = transcribe_audio(local_path, api_key)

        if not transcription:
            logger.error("Transcription failed.")
            return ""

        save_transcription_to_s3_and_dynamo(
            config_dict['bucket_name'],
            config_dict['chat_id'],
            config_dict['videocode'],
            transcription,
            config_dict['dynamo_table']
        )

        transcription_text = transcription.get('text', '')
        caption = record.get('caption', '')
        transcription_with_caption = f"{transcription_text} Caption: {caption}" if caption else transcription_text
        logger.info("Video transcribed")

    else:
        transcription = get_json_from_s3(transcribed_record['transcription_s3_key'])
        transcription_with_caption = transcription.get('text', '')

    return transcription_with_caption
