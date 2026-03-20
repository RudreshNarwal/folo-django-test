import boto3
from django.conf import settings
from uuid import uuid4
import base64
import logging
import phonenumbers
from phonenumbers import NumberParseException
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

def upload_to_s3(image_file, user_id, document_type, content_type):
    s3 = boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME
    )
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    folder_name = f"{user_id}"
    file_extension = image_file.name.split('.')[-1].lower()
    file_name = f"{document_type.lower()}_{user_id}.{file_extension}"
    s3_key = f"users/{folder_name}/{file_name}"

    try:
        s3.upload_fileobj(
            image_file,
            bucket_name,
            s3_key,
            ExtraArgs={
                'ContentType': content_type,
                # 'ACL': 'private'  # Ensure the file is not publicly accessible
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


def get_public_url(s3_key):
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    region_name = settings.AWS_S3_REGION_NAME
    url = f"https://{bucket_name}.s3.{region_name}.amazonaws.com/{s3_key}"
    return url


def generate_presigned_url(s3_key, expiration=3600):
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    region_name = settings.AWS_S3_REGION_NAME
    url = f"https://{bucket_name}.s3.{region_name}.amazonaws.com/{s3_key}"
    return url
    # s3 = boto3.client(
    #     's3',
    #     aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    #     aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    #     region_name=settings.AWS_S3_REGION_NAME
    # )
    # bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    # try:
    #     response = s3.generate_presigned_url(
    #         'get_object',
    #         Params={'Bucket': bucket_name, 'Key': s3_key, 'ResponseContentDisposition': 'inline'},
    #         ExpiresIn=expiration
    #     )
    #     return response
    # except Exception as e:
    #     logger.error(f"Error generating pre-signed URL: {e}")
    #     return None


# Add this mapping at the top of the file or create a new utils.py file if it doesn't exist
COUNTRY_CODE_TO_COUNTRY_MAPPING = {
    '+254': 'KE',  # Kenya
    '+1': 'US',  # United States
    '+44': 'GB',  # United Kingdom
    '+61': 'AU',  # Australia
    '+91': 'IN',  # India
    '+234': 'NG',  # Nigeria
    '+27': 'ZA',  # South Africa
    '+256': 'UG',  # Uganda
    '+255': 'TZ',  # Tanzania
    '+250': 'RW',  # Rwanda
    '+251': 'ET',  # Ethiopia
    '+233': 'GH',  # Ghana
    '+221': 'SN',  # Senegal
    '+225': 'CI',  # Côte d'Ivoire
    '+226': 'BF',  # Burkina Faso
    '+223': 'ML',  # Mali
    '+227': 'NE',  # Niger
    '+235': 'TD',  # Chad
    '+237': 'CM',  # Cameroon
    '+236': 'CF',  # Central African Republic
    '+242': 'CG',  # Congo
    '+243': 'CD',  # Democratic Republic of Congo
    '+241': 'GA',  # Gabon
    '+240': 'GQ',  # Equatorial Guinea
    '+244': 'AO',  # Angola
    '+260': 'ZM',  # Zambia
    '+263': 'ZW',  # Zimbabwe
    '+267': 'BW',  # Botswana
    '+264': 'NA',  # Namibia
    '+266': 'LS',  # Lesotho
    '+268': 'SZ',  # Eswatini
    '+258': 'MZ',  # Mozambique
    '+265': 'MW',  # Malawi
    '+261': 'MG',  # Madagascar
    '+230': 'MU',  # Mauritius
    '+248': 'SC',  # Seychelles
    '+269': 'KM',  # Comoros
    '+253': 'DJ',  # Djibouti
    '+252': 'SO',  # Somalia
    '+291': 'ER',  # Eritrea
    '+249': 'SD',  # Sudan
    '+211': 'SS',  # South Sudan
    '+20': 'EG',  # Egypt
    '+218': 'LY',  # Libya
    '+216': 'TN',  # Tunisia
    '+213': 'DZ',  # Algeria
    '+212': 'MA',  # Morocco
    '+222': 'MR',  # Mauritania
    '+86': 'CN',  # China
    '+81': 'JP',  # Japan
    '+82': 'KR',  # South Korea
    '+66': 'TH',  # Thailand
    '+84': 'VN',  # Vietnam
    '+63': 'PH',  # Philippines
    '+62': 'ID',  # Indonesia
    '+60': 'MY',  # Malaysia
    '+65': 'SG',  # Singapore
    '+880': 'BD',  # Bangladesh
    '+92': 'PK',  # Pakistan
    '+94': 'LK',  # Sri Lanka
    '+977': 'NP',  # Nepal
    '+975': 'BT',  # Bhutan
    '+95': 'MM',  # Myanmar
    '+855': 'KH',  # Cambodia
    '+856': 'LA',  # Laos
    '+976': 'MN',  # Mongolia
    '+93': 'AF',  # Afghanistan
    '+98': 'IR',  # Iran
    '+964': 'IQ',  # Iraq
    '+963': 'SY',  # Syria
    '+961': 'LB',  # Lebanon
    '+962': 'JO',  # Jordan
    '+972': 'IL',  # Israel
    '+970': 'PS',  # Palestine
    '+966': 'SA',  # Saudi Arabia
    '+967': 'YE',  # Yemen
    '+968': 'OM',  # Oman
    '+971': 'AE',  # UAE
    '+974': 'QA',  # Qatar
    '+973': 'BH',  # Bahrain
    '+965': 'KW',  # Kuwait
    '+90': 'TR',  # Turkey
    '+49': 'DE',  # Germany
    '+33': 'FR',  # France
    '+39': 'IT',  # Italy
    '+34': 'ES',  # Spain
    '+351': 'PT',  # Portugal
    '+31': 'NL',  # Netherlands
    '+32': 'BE',  # Belgium
    '+41': 'CH',  # Switzerland
    '+43': 'AT',  # Austria
    '+45': 'DK',  # Denmark
    '+46': 'SE',  # Sweden
    '+47': 'NO',  # Norway
    '+358': 'FI',  # Finland
    '+354': 'IS',  # Iceland
    '+353': 'IE',  # Ireland
    '+48': 'PL',  # Poland
    '+55': 'BR',  # Brazil
    '+54': 'AR',  # Argentina
    '+56': 'CL',  # Chile
    '+51': 'PE',  # Peru
    '+57': 'CO',  # Colombia
    '+58': 'VE',  # Venezuela
    '+52': 'MX',  # Mexico
    '+53': 'CU',  # Cuba
    '+64': 'NZ',  # New Zealand
    '+7': 'RU',  # Russia
}


def get_country_from_country_code(country_code):
    """
    Get the country field value based on the country code.

    Args:
        country_code (str): The country code (e.g., '+254')

    Returns:
        str: The country code for django-countries field (e.g., 'KE')
    """
    return COUNTRY_CODE_TO_COUNTRY_MAPPING.get(country_code, 'KE')  # Default to Kenya


def normalize_phone_number(phone_number, default_country='KE'):
    """
    Normalize a phone number to E164 format.
    
    Args:
        phone_number (str): Phone number to normalize
        default_country (str): Default country code if not in number
        
    Returns:
        str: Normalized phone number in E164 format (+254XXXXXXXXX)
        
    Raises:
        ValidationError: If phone number is invalid
    """
    try:
        # Remove any whitespace and common separators
        cleaned = str(phone_number).strip().replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        
        # Try parsing with default country first
        try:
            parsed = phonenumbers.parse(cleaned, default_country)
        except NumberParseException:
            # If that fails, try without country hint
            parsed = phonenumbers.parse(cleaned, None)
        
        # Validate the number
        if not phonenumbers.is_valid_number(parsed):
            raise ValidationError(f"Invalid phone number: {phone_number}")
        
        # Return E164 format
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        
    except NumberParseException as e:
        raise ValidationError(f"Could not parse phone number '{phone_number}': {str(e)}")
    except Exception as e:
        raise ValidationError(f"Error normalizing phone number: {str(e)}")


def get_phone_number_parts(phone_number, default_country='KE'):
    """
    Extract country code and national number from a phone number.
    
    Args:
        phone_number (str): Phone number to parse
        default_country (str): Default country code if not in number
        
    Returns:
        tuple: (country_code, national_number)
        Example: ('+254', '712345678')
        
    Raises:
        ValidationError: If phone number is invalid
    """
    try:
        cleaned = str(phone_number).strip().replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        
        try:
            parsed = phonenumbers.parse(cleaned, default_country)
        except NumberParseException:
            parsed = phonenumbers.parse(cleaned, None)
        
        if not phonenumbers.is_valid_number(parsed):
            raise ValidationError(f"Invalid phone number: {phone_number}")
        
        country_code = f"+{parsed.country_code}"
        national_number = str(parsed.national_number)
        
        return (country_code, national_number)
        
    except NumberParseException as e:
        raise ValidationError(f"Could not parse phone number '{phone_number}': {str(e)}")
    except Exception as e:
        raise ValidationError(f"Error parsing phone number: {str(e)}")