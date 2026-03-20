import base64
import os
from openai import OpenAI
from typing import Optional
from pydantic import BaseModel, Field


class IDCardData(BaseModel):
	first_name: str = Field(description="First name from the ID card")
	last_name: str = Field(description="Last name from the ID card")
	middle_name: Optional[str] = Field(None, description="Middle name if present on the ID card")
	date_of_birth: str = Field(description="Date of birth in YYYY-MM-DD format")
	gender: str = Field(description="Gender as shown on the ID card")
	nation_id: str = Field(description="National ID number from the card")
	district_of_birth: Optional[str] = Field(None, description="District of birth if shown on the ID card")


def get_base64_from_local_image(image_path: str) -> str:
	if not os.path.exists(image_path):
		raise FileNotFoundError(f"Image file not found: {image_path}")
	
	with open(image_path, 'rb') as image_file:
		return base64.b64encode(image_file.read()).decode('utf-8')


def get_mime_type(file_path: str) -> str:
	ext = file_path.lower().split('.')[-1]
	mime_types = {
		'jpg': 'image/jpeg',
		'jpeg': 'image/jpeg',
		'png': 'image/png',
		'heic': 'image/heic'
	}
	return mime_types.get(ext, 'image/jpeg')


def main():
	client = OpenAI(api_key="")
	
	try:
		front_image_path = "id_front.jpg"
		back_image_path = "id_back.jpg"
		
		front_base64 = get_base64_from_local_image(front_image_path)
		back_base64 = get_base64_from_local_image(back_image_path)
		
		messages = [
			{
				"role": "system",
				"content": """Extract the following information from the ID card images and return as JSON:
                {
                    "first_name": "First name",
                    "last_name": "Last name",
                    "middle_name": "Middle name if present",
                    "date_of_birth": "YYYY-MM-DD",
                    "gender": "Male/Female",
                    "nation_id": "ID number",
                    "district_of_birth": "District if shown"
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
							"url": f"data:{get_mime_type(front_image_path)};base64,{front_base64}"
						}
					},
					{
						"type": "image_url",
						"image_url": {
							"url": f"data:{get_mime_type(back_image_path)};base64,{back_base64}"
						}
					}
				]
			}
		]
		
		print("Analyzing ID card images...")
		collected_chunks = []
		collected_messages = []
		
		response = client.chat.completions.create(
			model="gpt-4o",
			messages=messages,
			max_tokens=500,
			temperature=0,
			response_format={"type": "json_object"},
			stream=True
		)
		
		for chunk in response:
			collected_chunks.append(chunk)
			chunk_message = chunk.choices[0].delta.content
			if chunk_message is not None:
				collected_messages.append(chunk_message)
				print(chunk_message, end="")
		
		full_reply_content = ''.join(collected_messages)
		extracted_data = IDCardData.parse_raw(full_reply_content)
		
		print("\nExtracted Data:")
		print(f"First Name: {extracted_data.first_name}")
		print(f"Middle Name: {extracted_data.middle_name}")
		print(f"Last Name: {extracted_data.last_name}")
		print(f"Date of Birth: {extracted_data.date_of_birth}")
		print(f"Gender: {extracted_data.gender}")
		print(f"National ID: {extracted_data.nation_id}")
		print(f"District of Birth: {extracted_data.district_of_birth}")
	
	except Exception as e:
		print(f"Error: {str(e)}")


if __name__ == "__main__":
	main()
