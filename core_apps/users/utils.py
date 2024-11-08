import boto3
from django.conf import settings
from uuid import uuid4
import base64
import logging

logger = logging.getLogger(__name__)

def upload_to_s3(image_file, user_id, document_type):
    s3 = boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME
    )
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    folder_name = f"{user_id}"
    file_extension = image_file.name.split('.')[-1].lower()
    file_name = f"{document_type.lower()}_{uuid4()}.{file_extension}"
    s3_key = f"users/{folder_name}/{file_name}"

    try:
        s3.upload_fileobj(
            image_file,
            bucket_name,
            s3_key,
            ExtraArgs={
                'ContentType': image_file.content_type,
                'ACL': 'private'  # Ensure the file is not publicly accessible
            }
        )
        return s3_key  # Return the S3 object key
    except Exception as e:
        logger.error(f"Error uploading to S3: {e}")
        raise

def get_base64_from_s3(s3_key):
    s3 = boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME
    )
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    try:
        obj = s3.get_object(Bucket=bucket_name, Key=s3_key)
        file_content = obj['Body'].read()
        base64_encoded = base64.b64encode(file_content).decode('utf-8')
        return base64_encoded
    except Exception as e:
        logger.error(f"Error reading from S3: {e}")
        raise

def generate_presigned_url(s3_key, expiration=3600):
    s3 = boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME
    )
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    try:
        response = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': s3_key},
            ExpiresIn=expiration
        )
        return response
    except Exception as e:
        logger.error(f"Error generating pre-signed URL: {e}")
        return None
