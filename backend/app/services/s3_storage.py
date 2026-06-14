import os
import logging
import boto3
from botocore.exceptions import ClientError
from typing import Optional
from app.config import get_settings

logger = logging.getLogger(__name__)

def upload_file_to_s3(file_data: bytes, filename: str, user_id: str) -> Optional[str]:
    """Uploads CV file data to AWS S3 bucket if credentials are set, returning the S3 URL.
    
    Returns None if S3 is not configured, fallback to local disk.
    """
    settings = get_settings()
    
    if not settings.s3_bucket_name or not settings.aws_access_key_id or not settings.aws_secret_access_key:
        logger.info("AWS S3 credentials not fully configured. Using local disk fallback for uploads.")
        return None

    s3_client = boto3.client(
        "s3",
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_region
    )
    
    # Prefix file to avoid naming collisions
    s3_key = f"cvs/{user_id}_{filename}"
    
    try:
        s3_client.put_object(
            Bucket=settings.s3_bucket_name,
            Key=s3_key,
            Body=file_data
        )
        s3_url = f"https://{settings.s3_bucket_name}.s3.{settings.aws_region}.amazonaws.com/{s3_key}"
        logger.info(f"Successfully uploaded file to AWS S3: {s3_url}")
        return s3_url
    except ClientError as e:
        logger.error(f"Failed to upload file to S3: {e}")
        # Return None to allow local disk fallback
        return None


def save_file_locally(file_data: bytes, filename: str, user_id: str) -> str:
    """Saves CV file data locally on the server disk under uploads/ directory."""
    # Ensure directory exists
    os.makedirs("uploads", exist_ok=True)
    
    safe_filename = f"{user_id}_{filename}"
    local_path = os.path.join("uploads", safe_filename)
    
    with open(local_path, "wb") as f:
        f.write(file_data)
        
    logger.info(f"Successfully saved file locally on disk: {local_path}")
    return local_path
