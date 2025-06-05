import json
import asyncio
import logging
import boto3
import re

from botocore.exceptions import ClientError
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from utils.instagram_utils import extract_shortcode_from_reel_url, load_reel
from utils.send_message_utils import (
    send_company_summary,
    send_general_summary,
    send_technology_summary,
)
from utils.aws_utils import SecretsManager, S3Manager, DynamoDBManager
from utils.summary_utils import get_summary
from utils.transcription_utils import get_transcription

# Initialize global resources
secrets_manager = SecretsManager()
secrets = secrets_manager.get_secret(secret_name="<your-secret>")

s3_manager = S3Manager(bucket_name="<your-s3-bucket>")
processed_videos_manager = DynamoDBManager(table_name="<your-dynamo-db-table>")

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def patch_event_body(body_dict: dict) -> dict:
    """
    Patch the incoming Telegram event to make it compatible with python-telegram-bot.

    Args:
        body_dict (dict): Raw Telegram webhook payload.

    Returns:
        dict: Patched body dictionary.
    """
    if "message" in body_dict:
        msg = body_dict["message"]
        msg["from"].setdefault("is_bot", False)
        msg["chat"].setdefault("type", "private")
    return body_dict


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /start command from users.

    Args:
        update (Update): Telegram update object.
        context (ContextTypes.DEFAULT_TYPE): Telegram context object.
    """
    await update.message.reply_text("Hello! Send me an Instagram reel link!")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Main handler for processing incoming messages and executing transcription/summarization.

    Args:
        update (Update): Telegram update object.
        context (ContextTypes.DEFAULT_TYPE): Telegram context object.
    """
    openai_api_key = secrets['<your-open-ai-secret-name>']
    message_text = update.message.text.strip()
    chat_id = str(update.message.chat.id)
    message_id = str(update.message.message_id)

    config_dict = {
        'chat_id': chat_id,
        'bucket_name': "<your-s3-bucket>",
        'dynamo_table': processed_videos_manager.table,
        'message_id': message_id,
    }

    if "instagram.com/reel" not in message_text:
        await update.message.reply_text(f"Echo: {message_text}")
        return

    await update.message.reply_text("Processing your reel...")

    videocode = extract_shortcode_from_reel_url(message_text)
    config_dict['videocode'] = videocode

    if not videocode:
        logger.warning("Could not extract videocode from message")
        await update.message.reply_text("Failed to extract videocode from the URL.")
        return

    record = processed_videos_manager.get_item(chat_id, videocode)

    video_dict = None
    if not record:
        video_dict = load_reel(config_dict, video_dict)
        if not video_dict:
            await update.message.reply_text("Failed to process your video.")
            return

        s3_manager.upload_file(
            video_dict['video_path'],
            chat_id,
            videocode
        )
        processed_videos_manager.save_item(video_dict)
        record = processed_videos_manager.get_item(chat_id, videocode)
    else:
        logger.info("This reel already exists in our database!")

    # Transcription
    await update.message.reply_text("Pre-processing completed, starting with transcription...")
    transcription = get_transcription(config_dict, video_dict, record, openai_api_key)

    # Summarization
    await update.message.reply_text("Transcription completed, creating summary...")
    summary_json = get_summary(config_dict, record, transcription, openai_api_key)
    logger.info(f"Summary message created - {summary_json}")
    await update.message.reply_text(f"Type : {summary_json['type']}")

    # Send summary message
    if summary_json['type'] == 'companies':
        await send_company_summary(update, summary_json)
    elif summary_json['type'] == 'technology':
        await send_technology_summary(update, summary_json)
    else:
        await send_general_summary(update, summary_json)

    await update.message.reply_text('Done')


def lambda_handler(event, context):
    """
    AWS Lambda entry point for handling Telegram bot updates.

    Args:
        event (dict): AWS Lambda event object.
        context: AWS Lambda context object.

    Returns:
        dict: Lambda response with statusCode and body.
    """

    async def main():
        bot_token = secrets['<your-telegram-bot-token>']
        application = Application.builder().token(bot_token).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        await application.initialize()
        await application.bot.initialize()

        body = json.loads(event["body"])
        patched_body = patch_event_body(body)

        update = Update.de_json(patched_body, application.bot)
        await application.process_update(update)
        await application.shutdown()

    asyncio.run(main())

    return {
        "statusCode": 200,
        "body": json.dumps("OK")
    }
