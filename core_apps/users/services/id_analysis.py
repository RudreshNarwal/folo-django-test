from typing import Optional, Tuple, Dict
import json
import logging
from datetime import datetime
from openai import OpenAI
from pydantic import BaseModel, Field
from django.conf import settings
from ..models.user import User, Document
from ..utils import get_base64_from_s3

logger = logging.getLogger(__name__)


class IDCardData(BaseModel):
	first_name: str = Field(description="First name from the ID card")
	last_name: str = Field(description="Last name from the ID card")
	middle_name: Optional[str] = Field(None, description="Middle name if present on the ID card")
	date_of_birth: str = Field(description="Date of birth in YYYY-MM-DD format")
	gender: str = Field(description="Gender as shown on the ID card")
	nation_id: str = Field(description="National ID number from the card")
	district_of_birth: Optional[str] = Field(None, description="District of birth if shown on the ID card")


class IDAnalysisService:
	@staticmethod
	def get_mime_type(s3_key: str) -> str:
		ext = s3_key.lower().split('.')[-1]
		mime_types = {
			'jpg': 'image/jpeg',
			'jpeg': 'image/jpeg',
			'png': 'image/png',
			'heic': 'image/heic'
		}
		return mime_types.get(ext, 'image/jpeg')
	
	@staticmethod
	def get_id_documents(user) -> Tuple[Document, Document]:
		"""Get front and back ID documents for a user."""
		front_doc = Document.objects.get(
			user=user,
			document_type='NATIONAL_IDENTITY'
		)
		back_doc = Document.objects.get(
			user=user,
			document_type='BACK_OF_NATIONAL_IDENTITY'
		)
		
		if not front_doc.s3_key or not back_doc.s3_key:
			raise ValueError("Missing S3 key for front and/or back document.")
		
		return front_doc, back_doc
	
	@classmethod
	def analyze_id_images(cls, front_s3_key: str, back_s3_key: str) -> IDCardData:
		"""Analyze ID card images using OpenAI's vision model."""
		# Get base64 encoded images
		front_image = get_base64_from_s3(front_s3_key)
		back_image = get_base64_from_s3(back_s3_key)
		
		client = OpenAI(api_key=settings.OPENAI_API_KEY)
		
		messages = [
			{
				"role": "system",
				"content": """Extract the following information from the ID card images and return it as a JSON object with these fields:
                {
                    "first_name": "First name from the ID card",
                    "last_name": "Last name from the ID card",
                    "middle_name": "Middle name if present (or null)",
                    "date_of_birth": "Date in YYYY-MM-DD format",
                    "gender": "Male or Female",
                    "nation_id": "National ID number",
                    "district_of_birth": "District of birth if shown (or null)"
                }"""
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
						"image_url": {
							"url": f"data:{cls.get_mime_type(front_s3_key)};base64,{front_image}"
						}
					},
					{
						"type": "image_url",
						"image_url": {
							"url": f"data:{cls.get_mime_type(back_s3_key)};base64,{back_image}"
						}
					}
				]
			}
		]
		
		completion = client.beta.chat.completions.parse(
			model="gpt-4o",
			messages=messages,
			response_format=IDCardData,
		)
		# Parse the response into IDCardData model
		idCardData = completion.choices[0].message.parsed
		return idCardData
	
	@staticmethod
	def update_user_data(user: User, extracted_data: IDCardData) -> None:
		"""Update user data with extracted information."""
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
		
		# Set national ID and district
		user.nation_id = extracted_data.nation_id
		user.district_of_birth = extracted_data.district_of_birth
		
		# Save the user
		user.save()
