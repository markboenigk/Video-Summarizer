import os
import re
import requests
import logging
import instaloader
from datetime import datetime
from telegram import Update
from utils.aws_utils import upload_file_to_s3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

TMP_DIR = '/tmp'  # AWS Lambda writable directory


def safe_filename(name: str) -> str:
    """
    Sanitize a filename by replacing unsafe characters with underscores.

    Args:
        name (str): The input filename string.

    Returns:
        str: A sanitized filename.
    """
    return re.sub(r'[^a-zA-Z0-9_-]', '_', name)


def extract_shortcode_from_reel_url(reel_url: str) -> str | None:
    """
    Extract the shortcode from an Instagram reel URL.

    Args:
        reel_url (str): The full reel URL.

    Returns:
        str | None: The shortcode if found, otherwise None.
    """
    pattern = r"https:\/\/www\.instagram\.com\/reel\/([a-zA-Z0-9_-]+)"
    match = re.search(pattern, reel_url)
    if match:
        return match.group(1)

    logger.warning(f"URL does not match expected pattern: {reel_url}")
    return None


def download_reel(shortcode: str) -> dict:
    """
    Download an Instagram reel video and return its metadata.

    Args:
        shortcode (str): The shortcode of the Instagram reel.

    Returns:
        dict: Metadata dictionary including local file path and video properties.

    Raises:
        ValueError: If the shortcode is invalid or the post is not a video.
        requests.HTTPError: If the video download fails.
    """
    if not shortcode:
        raise ValueError("Invalid shortcode, cannot download reel.")

    loader = instaloader.Instaloader()
    post = instaloader.Post.from_shortcode(loader.context, shortcode)

    if not post.is_video:
        raise ValueError("Provided shortcode is not a video (reel).")

    created_date = post.date_utc.strftime("%Y-%m-%d%H:%M:%S")
    creator_username = post.owner_username
    output_path = os.path.join(
        TMP_DIR, f"{created_date}_{creator_username}_reel_{safe_filename(shortcode)}.mp4"
    )

    video_url = post.video_url
    logger.info(f"Downloading video from: {video_url}")

    response = requests.get(video_url, stream=True)
    response.raise_for_status()

    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    logger.info(f"Video downloaded to: {output_path}")

    return {
        'videocode': shortcode,
        'url': post.video_url,
        'video_path': output_path,
        'creator': creator_username,
        'caption': post.caption,
        'post_date': post.date_utc,
        'duration': post.video_duration,
        'processing_timestamp': datetime.now().isoformat(),
    }


def update_video_dict(
    video_dict: dict,
    chat_id: str,
    message_id: str,
    video_type: str
) -> dict:
    """
    Add metadata and S3 path information to the video dictionary.

    Args:
        video_dict (dict): The original video metadata.
        chat_id (str): Telegram chat ID.
        message_id (str): Telegram message ID.
        video_type (str): Type of video (e.g., 'reel').

    Returns:
        dict: The updated video dictionary with S3 path and extra metadata.
    """
    video_dict.update({
        'chat_id': chat_id,
        'message_id': message_id,
        'is_transcribed': False,
        'is_summarized': False,
        'type': video_type,
    })

    filename = os.path.basename(video_dict['video_path'])
    s3_key = f"{chat_id}/{message_id}/{filename}"
    video_dict['s3_video_path'] = s3_key

    return video_dict


def process_reel_metadata(shortcode: str, chat_id: str, message_id: str) -> dict:
    """
    Process an Instagram reel and return its metadata.

    Args:
        shortcode (str): The Instagram shortcode of the reel.
        chat_id (str): Telegram chat ID.
        message_id (str): Telegram message ID.

    Returns:
        dict: The processed video metadata dictionary.
    """
    video_dict = download_reel(shortcode)
    return update_video_dict(video_dict, chat_id, message_id, video_type="reel")


async def send_reel_metadata(update: Update, video: dict) -> None:
    """
    Send video metadata back to the user via Telegram.

    Args:
        update (Update): The Telegram update.
        video (dict): The video metadata dictionary.
    """
    metadata = (
        f"Creator: {video['creator']}\n"
        f"Date: {video['post_date']}\n"
        f"Duration: {video['duration']} seconds\n"
        f"Caption: {video['caption']}"
    )
    await update.message.reply_text(metadata)


def load_reel(config_dict: dict, video_dict: dict = None) -> dict | None:
    """
    Load and process a reel from a configuration dictionary.

    Args:
        config_dict (dict): Dictionary containing 'videocode', 'chat_id', and 'message_id'.
        video_dict (dict, optional): Existing video dictionary to update.

    Returns:
        dict | None: The updated video dictionary, or None if an error occurs.
    """
    try:
        video_dict = download_reel(config_dict['videocode'])
        return update_video_dict(
            video_dict,
            config_dict['chat_id'],
            config_dict['message_id'],
            video_type='reel'
        )
    except Exception as e:
        logger.error(f"Error processing reel: {e}", exc_info=True)
        return None
