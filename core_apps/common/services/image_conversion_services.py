import requests
import base64
from io import BytesIO


def get_image_data_uri_from_signed_url(signed_url: str, content_type: str = "image/jpeg") -> str or None:
    """
    Downloads an image from a signed AWS URL and converts it to a data URI (data:image/jpg;base64,...).

    Args:
        signed_url (str): The pre-signed URL to the image in AWS S3.
        content_type (str): The MIME type of the image (e.g., "image/jpeg", "image/png").
                            This is crucial for the data URI prefix. Defaults to "image/jpeg".

    Returns:
        str: The data URI string (e.g., "data:image/jpeg;base64,..."), or None if an error occurs.
    """
    try:
        # 1. Download the image from the signed URL
        response = requests.get(signed_url)
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)

        # 2. Get the raw image content (bytes)
        image_bytes = BytesIO(response.content)

        # 3. Encode the image bytes to base64
        encoded_string = base64.b64encode(image_bytes.getvalue()).decode('utf-8')

        # 4. Construct the data URI
        data_uri = f"data:{content_type};base64,{encoded_string}"
        return data_uri

    except requests.exceptions.RequestException as e:
        print(f"Error downloading image from URL: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None
