from typing import Optional
from pydantic import BaseModel, Field
from celery import shared_task
from django.conf import settings
from openai import OpenAI
from celery.utils.log import get_task_logger
from .utils import get_base64_from_s3
from .models.user import UserTask, User
from datetime import datetime

logger = get_task_logger(__name__)


class IDCardData(BaseModel):
    first_name: str = Field(description="First name from the ID card")
    last_name: str = Field(description="Last name from the ID card")
    middle_name: Optional[str] = Field(None, description="Middle name if present on the ID card")
    date_of_birth: str = Field(description="Date of birth in YYYY-MM-DD format")
    gender: str = Field(description="Gender as shown on the ID card")
    nation_id: str = Field(description="National ID number from the card")
    district_of_birth: Optional[str] = Field(None, description="District of birth if shown on the ID card")


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
        # Get base64 encoded images using existing utility
        front_image = get_base64_from_s3(front_s3_key)
        back_image = get_base64_from_s3(back_s3_key)
        
        def get_mime_type(s3_key: str) -> str:
            ext = s3_key.lower().split('.')[-1]
            mime_types = {
                'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg',
                'png': 'image/png',
                'heic': 'image/heic'
            }
            return mime_types.get(ext, 'image/jpeg')

        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
        messages = [
            {
                "role": "system",
                "content": """Extract the following information from the ID card images:
                - First name
                - Last name
                - Middle name (if present)
                - Date of birth (in YYYY-MM-DD format)
                - Gender (Male/Female)
                - National ID number
                - District of birth (if shown)"""
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Extract the required information from these ID card images."
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{get_mime_type(front_s3_key)};base64,{front_image}"}
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{get_mime_type(back_s3_key)};base64,{back_image}"}
                    }
                ]
            }
        ]

        extracted_data = None
        with client.beta.chat.completions.stream(
            model="gpt-4o",
            messages=messages,
            response_format=IDCardData,
            max_tokens=500,
            temperature=0
        ) as stream:
            for event in stream:
                if event.type == "content.delta":
                    if event.parsed is not None:
                        logger.info(f"Received parsed data: {event.parsed}")
                        extracted_data = event.parsed
                elif event.type == "content.done":
                    logger.info("Completed parsing ID card data")
                elif event.type == "error":
                    error_msg = f"Error in stream: {event.error}"
                    logger.error(error_msg)
                    task.mark_failed(error_msg)
                    raise Exception(error_msg)

            final_completion = stream.get_final_completion()
            if final_completion and extracted_data:
                try:
                    # Update the user data
                    user = task.user
                    user.first_name = extracted_data.first_name
                    user.last_name = extracted_data.last_name
                    user.middle_name = extracted_data.middle_name
                    
                    # Convert date string to datetime.date object
                    dob = datetime.strptime(extracted_data.date_of_birth, '%Y-%m-%d').date()
                    user.dob = dob
                    
                    # Map gender to choices
                    gender_mapping = {
                        'Male': User.Gender.MALE,
                        'Female': User.Gender.FEMALE,
                        'Other': User.Gender.OTHER
                    }
                    user.gender = gender_mapping.get(extracted_data.gender, User.Gender.OTHER)
                    
                    # Set national ID
                    user.nation_id = extracted_data.nation_id
                    user.district_of_birth = extracted_data.district_of_birth
                    
                    # Save the user
                    user.save()
                    
                    # Mark task as completed with the extracted data
                    logger.info(f"Successfully analyzed ID images and updated user data for task {task_id}")
                    task.mark_completed(extracted_data.dict())
                    return extracted_data.dict()
                    
                except Exception as update_error:
                    error_msg = f"Error updating user data: {str(update_error)}"
                    logger.error(error_msg)
                    task.mark_failed(error_msg)
                    raise
            else:
                error_msg = "No data extracted from ID card images"
                logger.error(error_msg)
                task.mark_failed(error_msg)
                raise Exception(error_msg)
            
    except Exception as e:
        error_msg = f"Error analyzing ID images: {str(e)}"
        logger.error(error_msg)
        task.mark_failed(error_msg)
        raise self.retry(exc=e)
