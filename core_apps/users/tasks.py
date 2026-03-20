from typing import Optional
from celery import shared_task
from django.conf import settings
from openai import OpenAI
from celery.utils.log import get_task_logger

from .services.id_analysis import IDAnalysisService
from .utils import get_base64_from_s3
from .models.user import UserTask, User
from datetime import datetime

logger = get_task_logger(__name__)



@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 2},
    retry_backoff=True
)
def analyze_id_images(self, task_id: str, front_s3_key: str, back_s3_key: str):
    """
    Analyze ID card images using OpenAI's vision model and update user data.
    """
    task = UserTask.objects.get(task_id=task_id)
    try:
        # Use the service to analyze images
        extracted_data = IDAnalysisService.analyze_id_images(front_s3_key, back_s3_key)
        
        # Update user data
        IDAnalysisService.update_user_data(task.user, extracted_data)
        
        # Mark task as completed with the extracted data
        logger.info(f"Successfully analyzed ID images and updated user data for task {task_id}")
        task.mark_completed(extracted_data.dict())
        return extracted_data.dict()
        
    except Exception as e:
        error_msg = f"Error analyzing ID images: {str(e)}"
        logger.error(error_msg)
        task.mark_failed(error_msg)
        raise self.retry(exc=e)
