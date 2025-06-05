import os
import json
import boto3
import logging
from decimal import Decimal
from datetime import datetime
from botocore.exceptions import ClientError
from boto3.resources.factory import ServiceResource
from boto3.dynamodb.conditions import Key, Attr
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class SecretsManager:
    """
    A utility class to retrieve secrets from AWS Secrets Manager with caching.
    """

    def __init__(self, region_name: str = "us-east-1"):
        """
        Initialize the SecretsManager client and cache.

        Args:
            region_name (str): AWS region where Secrets Manager is located.
        """
        self.client = boto3.client('secretsmanager', region_name=region_name)
        self._cache = {}

    def get_secret(self, secret_name: str) -> dict:
        """
        Retrieve a secret from Secrets Manager. Uses an internal cache to avoid redundant API calls.

        Args:
            secret_name (str): The name of the secret.

        Returns:
            dict: The secret content parsed as JSON.
        """
        if secret_name in self._cache:
            return self._cache[secret_name]

        try:
            response = self.client.get_secret_value(SecretId=secret_name)
            secret = json.loads(response['SecretString'])
            self._cache[secret_name] = secret
            return secret
        except ClientError as e:
            logger.error(f"Error retrieving secret {secret_name}: {e}")
            raise


class S3Manager:
    """
    A utility class for managing file and JSON operations in an S3 bucket.
    """

    def __init__(self, bucket_name: str):
        """
        Initialize the S3Manager.

        Args:
            bucket_name (str): The name of the S3 bucket.
        """
        self.bucket_name = bucket_name
        self.client = boto3.client('s3')

    def upload_file(self, file_path: str, chat_id: str, videocode: str) -> str:
        """
        Upload a file to S3.

        Args:
            file_path (str): Path to the local file.
            chat_id (str): Chat identifier.
            videocode (str): Video code.

        Returns:
            str: The S3 key of the uploaded file.
        """
        file_path = file_path.replace(" ", "_").strip()
        filename = os.path.basename(file_path)
        s3_key = f"{chat_id}/{videocode}/{filename}"

        self.client.upload_file(file_path, self.bucket_name, s3_key)
        logger.info(f"Uploaded file to S3: {s3_key}")

        return s3_key

    def download_file(self, file_key: str) -> str | None:
        """
        Download a file from S3 to the /tmp directory.

        Args:
            file_key (str): The S3 key of the file.

        Returns:
            str | None: The local file path if successful, otherwise None.
        """
        local_path = f"/tmp/{os.path.basename(file_key)}"

        try:
            self.client.download_file(self.bucket_name, file_key, local_path)
            return local_path
        except Exception as e:
            logger.error(f"Error downloading file from S3: {e}")
            return None

    def put_json(self, key: str, content: dict) -> None:
        """
        Upload a JSON object to S3.

        Args:
            key (str): The S3 key where the JSON should be stored.
            content (dict): The content to store.
        """
        self.client.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=json.dumps(content),
            ContentType='application/json'
        )

    def get_json(self, key: str) -> dict:
        """
        Retrieve a JSON object from S3.

        Args:
            key (str): The S3 key of the JSON object.

        Returns:
            dict: The parsed JSON content.

        Raises:
            ClientError: If the retrieval fails.
        """
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=key)
            return json.loads(response['Body'].read().decode('utf-8'))
        except ClientError as e:
            logger.error(f"Error retrieving JSON from S3: {e}")
            raise


class DynamoDBManager:
    """
    A utility class for managing DynamoDB operations.
    """

    def __init__(self, table_name: str, region_name: str = "us-east-1"):
        """
        Initialize the DynamoDBManager.

        Args:
            table_name (str): The name of the DynamoDB table.
            region_name (str): The AWS region.
        """
        self.resource = boto3.resource("dynamodb", region_name=region_name)
        self.table = self.resource.Table(table_name)

    def save_item(self, item: dict) -> None:
        """
        Save an item to the DynamoDB table, converting values to safe types.

        Args:
            item (dict): The item to store.
        """

        def safe(val):
            if isinstance(val, float):
                return Decimal(str(val))
            elif isinstance(val, (str, int, bool, type(None))):
                return val
            elif isinstance(val, (list, dict)):
                return json.dumps(val)
            return str(val)

        safe_item = {k: safe(v) for k, v in item.items()}
        self.table.put_item(Item=safe_item)

    def get_item(self, chat_id: str, videocode: str) -> dict | None:
        """
        Retrieve a specific item from DynamoDB by chat ID and video code.

        Args:
            chat_id (str): The chat identifier.
            videocode (str): The video code.

        Returns:
            dict | None: The item if found, else None.
        """
        response = self.table.get_item(
            Key={
                'chat_id': chat_id,
                'videocode': videocode
            }
        )
        return response.get("Item")


def upload_file_to_s3(
    file_path: str,
    bucket_name: str,
    chat_id: str,
    videocode: str
) -> str:
    """
    Upload a file to S3 using basic boto3 client.

    Args:
        file_path (str): Path to the file.
        bucket_name (str): The S3 bucket name.
        chat_id (str): The chat ID.
        videocode (str): The video code.

    Returns:
        str: The S3 key of the uploaded file.
    """
    file_path = file_path.replace(" ", "_").strip()
    s3 = boto3.client("s3")
    filename = os.path.basename(file_path)
    s3_key = f"{chat_id}/{videocode}/{filename}"

    s3.upload_file(file_path, bucket_name, s3_key)
    logger.info(f"Uploaded file to S3: {s3_key}")

    return s3_key

def get_json_from_s3(s3_key: str) -> dict:
    """
    Retrieves and parses JSON from S3.
    
    Args:
        s3_key (str): The S3 key where the JSOn file is stored
        
    Returns:
        dict: The parsed JSON content
    """
    s3 = boto3.client('s3')
    try:
        # Get the object from S3
        response = s3.get_object(
            Bucket='<your-s3-bucket>',
            Key=s3_key
        )
        
        # Read and parse the JSON content
        json_content = response['Body'].read().decode('utf-8')
        json_data = json.loads(json_content)
        return json_data
        
    except ClientError as e:
        logger.error(f"Error retrieving JSON from S3: {e}")
        raise


def update_dynamo_record_with_transcription(
    table,
    chat_id: str,
    videocode: str,
    transcription_summary_s3_key: str
):
    """
    Updates the DynamoDB record for a given chat_id and videocode,
    marking it as transcribed and saving the S3 key for the transcription summary.

    Parameters:
        table: DynamoDB Table resource
        chat_id (str): Telegram chat ID (partition key)
        videocode (str): Instagram reel shortcode (sort key)
        transcription_summary_s3_key (str): S3 key to the transcription summary

    Returns:
        dict: The response from DynamoDB update_item call
    """
    update_expr = "SET is_transcribed = :transcribed, transcription_summary_s3_key = :s3key"
    expr_attr_values = {
        ":transcribed": True,
        ":s3key": transcription_summary_s3_key,
    }

    response = table.update_item(
        Key={
            'chat_id': chat_id,
            'videocode': videocode
        },
        UpdateExpression=update_expr,
        ExpressionAttributeValues=expr_attr_values
    )

    return response

def check_video_exists(
    table: ServiceResource,
    chat_id: str,
    shortcode: str
) -> bool:
    """
    Checks whether a video record exists in DynamoDB.

    Args:
        table (ServiceResource): The DynamoDB table resource.
        chat_id (str): The chat ID.
        shortcode (str): The short video code.

    Returns:
        bool: True if the video exists, else False.
    """
    response = table.query(
        KeyConditionExpression=Key('chat_id').eq(chat_id) & Key('videocode').eq(shortcode)
    )
    return response['Count'] > 0


def get_not_transcribed_video(table: ServiceResource, chat_id: str, shortcode: str) -> dict:
    """
    Queries DynamoDB for a reel (Instagram video) that has not yet been transcribed,
    based on the provided chat ID and reel shortcode.

    Parameters:
        table (ServiceResource): The DynamoDB table resource.
        chat_id (str): The Telegram chat ID used as the partition key.
        shortcode (str): The Instagram reel shortcode used as the sort key.

    Returns:
        dict: The first matching reel record that has not been transcribed.
              Returns None if no such item exists.
    """
    response = table.query(
        KeyConditionExpression=Key('chat_id').eq(chat_id) & Key('videocode').eq(shortcode)
    )

    for item in response.get('Items', []):
        if not item.get("is_transcribed", False):  # Return only if not transcribed
            return item

    return None

def save_video_transcription_and_summary_to_s3(
    bucket: str,
    chat_id: str,
    message_id: str,
    videocode: str,
    transcription: dict,
    parsed_output
) -> str:
    """
    Saves both the transcription and summary to S3 in a single combined JSON file.

    Args:
        bucket (str): The name of the S3 bucket.
        chat_id (str): The chat ID.
        message_id (str): The Telegram message ID.
        videocode (str): The video code.
        transcription (dict): The transcription data.
        parsed_output: A Pydantic model of the parsed summary.

    Returns:
        str: The S3 key of the combined file.
    """
    s3 = boto3.client('s3')
    now = datetime.utcnow().isoformat()

    s3_key = f"{chat_id}/{message_id}/{videocode}_transcription_summary.json"
    content = {
        "chat_id": chat_id,
        "message_id": message_id,
        "videocode": videocode,
        "timestamp": now,
        "reel_owner": transcription.get("owner", "unknown"),
        "transcription": transcription["text"],
        "summary": parsed_output.dict()
    }

    s3.put_object(
        Bucket=bucket,
        Key=s3_key,
        Body=json.dumps(content),
        ContentType='application/json'
    )

    return s3_key

def get_transcribed_video(table: ServiceResource, chat_id: str, videocode: str) -> dict:
    """
    Retrieves a transcribed reel record from DynamoDB.
    
    Args:
        table (ServiceResource): The DynamoDB table resource
        chat_id (str): The chat ID
        videocode (str): The video code
        
    Returns:
        dict: The DynamoDB record if found and transcribed, None otherwise
    """
    response = table.query(
        KeyConditionExpression=Key('chat_id').eq(chat_id) & Key('videocode').eq(videocode)
    )
    
    for item in response.get('Items', []):
        if item.get("is_transcribed", False):  # Return only if transcribed
            return item
            
    return None


def get_summarized_video(table: ServiceResource, chat_id: str, videocode: str) -> dict:
    """
    Retrieves a summarized reel record from DynamoDB.
    
    Args:
        table (ServiceResource): The DynamoDB table resource
        chat_id (str): The chat ID
        videocode (str): The video code
        
    Returns:
        dict: The DynamoDB record if found and summarized None otherwise
    """
    response = table.query(
        KeyConditionExpression=Key('chat_id').eq(chat_id) & Key('videocode').eq(videocode)
    )
    
    for item in response.get('Items', []):
        if item.get("is_summarized", False):  # Return only if summarized
            return item
            
    return None


def save_transcription_to_s3_and_dynamo(
    bucket_name: str,
    chat_id: str,
    videocode: str,
    transcription: dict,
    dynamo_table: ServiceResource
) -> str:
    """
    Saves the transcription to S3 and updates the DynamoDB record with its location.

    Args:
        bucket_name (str): The name of the S3 bucket.
        chat_id (str): The chat ID.
        videocode (str): The video code.
        transcription (dict): The transcription content.
        dynamo_table (ServiceResource): The DynamoDB table resource.

    Returns:
        str: The S3 key of the stored transcription.
    """
    s3_client = boto3.client('s3')
    s3_key = f"{chat_id}/{videocode}/transcription.json"

    s3_client.put_object(
        Bucket=bucket_name,
        Key=s3_key,
        Body=json.dumps(transcription),
        ContentType='application/json'
    )

    dynamo_table.update_item(
        Key={'chat_id': chat_id, 'videocode': videocode},
        UpdateExpression="SET is_transcribed = :true, transcription_s3_key = :key",
        ExpressionAttributeValues={
            ':true': True,
            ':key': s3_key
        }
    )

    return s3_key


def save_summary_to_s3_and_dynamo(
    bucket_name: str,
    chat_id: str,
    videocode: str,
    parsed_output,
    dynamo_table: ServiceResource
) -> str:
    """
    Saves the parsed summary to S3 and updates the DynamoDB record.

    Args:
        bucket_name (str): The name of the S3 bucket.
        chat_id (str): The chat ID.
        videocode (str): The video code.
        parsed_output: A Pydantic model containing the summary.
        dynamo_table (ServiceResource): The DynamoDB table resource.

    Returns:
        str: The S3 key of the stored summary.
    """
    s3_client = boto3.client('s3')
    s3_key = f"{chat_id}/{videocode}/summary.json"

    s3_client.put_object(
        Bucket=bucket_name,
        Key=s3_key,
        Body=json.dumps(parsed_output.model_dump()),
        ContentType='application/json'
    )

    summary_type = parsed_output.type

    dynamo_table.update_item(
        Key={'chat_id': chat_id, 'videocode': videocode},
        UpdateExpression="""
            SET is_summarized = :true,
                summary_s3_key = :key,
                summary_type = :summary_type
        """,
        ExpressionAttributeValues={
            ':true': True,
            ':key': s3_key,
            ':summary_type': summary_type
        }
    )

    return s3_key

def get_video_path_from_s3(
    dynamodb_table: ServiceResource,
    chat_id: str,
    videocode: str) -> str | None:
    """
    Retrieves the S3 video path from DynamoDB.

    Args:
        dynamodb_table (ServiceResource): The DynamoDB table resource.
        chat_id (str): The chat ID.
        videocode (str): The video code.

    Returns:
        str | None: The S3 video path if found, else None.
    """
    response = dynamodb_table.query(
        KeyConditionExpression=Key('chat_id').eq(chat_id) & Key('videocode').eq(videocode)
    )
    for item in response.get('Items', []):
        if 's3_video_path' in item:
            return item['s3_video_path']
    return None


def update_dynamo_record_with_transcription(
    table,
    chat_id: str,
    videocode: str,
    transcription_summary_s3_key: str
):
    """
    Updates the DynamoDB record for a given chat_id and videocode,
    marking it as transcribed and saving the S3 key for the transcription summary.

    Parameters:
        table: DynamoDB Table resource
        chat_id (str): Telegram chat ID (partition key)
        videocode (str): Instagram reel shortcode (sort key)
        transcription_summary_s3_key (str): S3 key to the transcription summary

    Returns:
        dict: The response from DynamoDB update_item call
    """
    update_expr = "SET is_transcribed = :transcribed, transcription_summary_s3_key = :s3key"
    expr_attr_values = {
        ":transcribed": True,
        ":s3key": transcription_summary_s3_key,
    }

    response = table.update_item(
        Key={
            'chat_id': chat_id,
            'videocode': videocode
        },
        UpdateExpression=update_expr,
        ExpressionAttributeValues=expr_attr_values
    )

    return response

def load_video_file_from_s3(bucket_name: str, file_key: str) -> str | None:
    """
    Downloads a video file from S3 to the local /tmp directory.

    Args:
        bucket_name (str): The name of the S3 bucket.
        file_key (str): The S3 key for the file.

    Returns:
        str | None: The local file path if download succeeds, else None.
    """
    s3 = boto3.client('s3')
    local_file_path = f"/tmp/{os.path.basename(file_key)}"

    try:
        s3.download_file(bucket_name, file_key, local_file_path)
        print(f"File downloaded from S3: {local_file_path}")
        return local_file_path
    except Exception as e:
        print(f"Error downloading file from S3: {e}")
        return None


def get_video_record(table: ServiceResource, chat_id: str, videocode: str) -> dict:
    """
    Retrieves the video record from DynamoDB.

    Args:
        table (ServiceResource): The DynamoDB table resource
        chat_id (str): The chat ID
        videocode (str): The video code

    Returns:
        dict: The full DynamoDB record if found, else None
    """
    response = table.query(
        KeyConditionExpression=Key('chat_id').eq(chat_id) & Key('videocode').eq(videocode)
    )
    items = response.get('Items', [])
    return items[0] if items else None