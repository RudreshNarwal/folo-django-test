from rest_framework import serializers

from core_apps.users.models import User
from django_countries.serializer_fields import CountryField
from phonenumber_field.serializerfields import PhoneNumberField
from rest_framework import serializers
from django_countries.serializer_fields import CountryField
from ..models.user import User, Document, Address
from ..utils import upload_to_s3, generate_presigned_url, get_country_from_country_code
import base64
from django.core.files.base import ContentFile


class DocumentSerializer(serializers.ModelSerializer):
	base64_encoded_document = serializers.CharField(write_only=True, required=True)
	signed_s3_url = serializers.SerializerMethodField(read_only=True)
	media_type = serializers.CharField(read_only=True)  # Make media_type read-only
	document_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
	
	class Meta:
		model = Document
		fields = ['id', 'document_type', 'media_type', 'signed_s3_url', 'base64_encoded_document', 'document_number']
	
	def get_signed_s3_url(self, obj):
		"""
		Generate a presigned URL for accessing the uploaded document.
		"""
		return generate_presigned_url(obj.s3_key)
	
	def validate_base64_encoded_document(self, value):
		"""
		Validate that the base64_encoded_document is properly formatted and does not exceed the size limit.
		"""
		try:
			# Split the base64 string to extract the media type and the actual data
			format, imgstr = value.split(';base64,')
			decoded_file = base64.b64decode(imgstr)
		except (ValueError, AttributeError, base64.binascii.Error):
			raise serializers.ValidationError("Invalid base64 encoded document.")
		
		# Check the file size (limit to 5MB)
		if len(decoded_file) > 5 * 1024 * 1024:  # 5MB limit
			raise serializers.ValidationError("File size exceeds the limit of 5MB.")
		
		# Validate the media_type
		media_type = format.split(':')[1] if ':' in format else 'application/octet-stream'
		allowed_types = ['image/jpeg', 'image/png', 'image/heif', 'image/heic', 'image/webp']
		if media_type not in allowed_types:
			raise serializers.ValidationError("Unsupported file type.")
		
		return value
	
	def create(self, validated_data):
		"""
		Handle the creation of a Document instance, including decoding the base64 document,
		uploading to S3, and saving the instance to the database.
		"""
		base64_encoded_document = validated_data.pop('base64_encoded_document')
		user = self.context['request'].user
		
		# Decode the base64 content
		try:
			format, imgstr = base64_encoded_document.split(';base64,')
			media_type = format.split(':')[1] if ':' in format else 'application/octet-stream'
			ext = format.split('/')[-1]
			decoded_file = base64.b64decode(imgstr)
		except (ValueError, AttributeError, base64.binascii.Error):
			raise serializers.ValidationError("Invalid base64 encoded document")
		
		# Create a ContentFile for the decoded document
		file_name = f"{validated_data['document_type']}.{ext}"
		content_file = ContentFile(decoded_file, name=file_name)
		
		# Upload the ContentFile to S3 with media_type as content_type
		s3_key = upload_to_s3(content_file, user.id, validated_data['document_type'], media_type)
		
		# Update or create the Document instance
		document, created = Document.objects.update_or_create(
			user=user,
			document_type=validated_data['document_type'],
			defaults={
				's3_key': s3_key,
				'media_type': media_type,
				'document_number': validated_data.get('document_number', None),
			}
		)
		return document


class AddressSerializer(serializers.ModelSerializer):
	country = CountryField()  # Properly handle CountryField
	
	class Meta:
		model = Address
		fields = [
			'address_type', 'city', 'country', 'line1', 'line2', 'state', 'code', 'country_master', 'state_master'
		]


class UserSerializer(serializers.ModelSerializer):
	mobile = serializers.CharField(required=True, max_length=15, min_length=5)
	country_code = serializers.CharField(max_length=5, allow_blank=True, allow_null=True, required=False)
	nation_id = serializers.CharField(required=True, max_length=20)
	first_name = serializers.CharField(required=True, max_length=128)
	middle_name = serializers.CharField(required=False, max_length=128, allow_null=True, allow_blank=True)
	last_name = serializers.CharField(required=False, max_length=128, allow_null=True, allow_blank=True)
	email = serializers.EmailField(required=True)
	dob = serializers.DateField(required=True)
	documents = DocumentSerializer(many=True, read_only=True)
	address = AddressSerializer(read_only=True)
	country = CountryField()  # Properly handle CountryField
	
	class Meta:
		model = User
		fields = [
			"pkid", "id", "first_name", "middle_name", "last_name", "dob", "mobile", 'is_mobile_verified', "email",
			"gender", "nation_id", "is_email_verified", "country_code", "marital_status", "country", "city", "title",
			"documents", "address", "district_of_birth", "employment_status", "expected_monthly_payments",
			"acting_as_intermediary", "occupation", "account_purpose", "account_purpose_other", "source_of_funds"
		]
	
	def validate_mobile(self, value):
		# Get country code from request body first
		request_country_code = self.initial_data.get('country_code')
		
		# Comprehensive list of country code prefixes
		country_code_prefixes = [
			'+254', '+1', '+44', '+61', '+91', '+234', '+27', '+256', '+255', '+250',
			'+251', '+233', '+221', '+225', '+226', '+223', '+227', '+235', '+237',
			'+236', '+242', '+243', '+241', '+240', '+244', '+260', '+263', '+267',
			'+264', '+266', '+268', '+258', '+265', '+261', '+230', '+248', '+269',
			'+253', '+252', '+291', '+249', '+211', '+20', '+218', '+216', '+213',
			'+212', '+222', '+231', '+232', '+224', '+245', '+238', '+220', '+228',
			'+229', '+86', '+81', '+82', '+66', '+84', '+63', '+62', '+60', '+65',
			'+880', '+92', '+94', '+977', '+975', '+95', '+855', '+856', '+976',
			'+93', '+98', '+964', '+963', '+961', '+962', '+972', '+970', '+966',
			'+967', '+968', '+971', '+974', '+973', '+965', '+90', '+357', '+995',
			'+374', '+994', '+7', '+998', '+993', '+992', '+996', '+49', '+33',
			'+39', '+34', '+351', '+31', '+32', '+352', '+41', '+43', '+45', '+46',
			'+47', '+358', '+354', '+353', '+48', '+420', '+421', '+36', '+386',
			'+385', '+387', '+381', '+382', '+389', '+355', '+30', '+359', '+40',
			'+373', '+380', '+375', '+370', '+371', '+372', '+55', '+54', '+56',
			'+51', '+57', '+58', '+593', '+591', '+595', '+598', '+592', '+597',
			'+594', '+52', '+502', '+501', '+503', '+504', '+505', '+506', '+507',
			'+53', '+509', '+64', '+679', '+675', '+677', '+678', '+687', '+689',
			'+676', '+685', '+686', '+688', '+674', '+680', '+691', '+692', '+682',
			'+683', '+690', '+681'
		]
		
		# Initialize variables
		mobile_number = value
		country_code = None
		
		# Check if mobile number already contains a country code prefix
		for prefix in country_code_prefixes:
			if value.startswith(prefix):
				country_code = prefix
				mobile_number = value[len(prefix):]
				break
		
		# If no country code found in mobile number, determine from other sources
		if country_code is None:
			# First priority: country code from request body
			if request_country_code and request_country_code in country_code_prefixes:
				country_code = request_country_code
			# Second priority: existing user's country code from database
			elif hasattr(self, 'instance') and self.instance and self.instance.country_code:
				country_code = self.instance.country_code
			# Third priority: default fallback
			else:
				country_code = '+254'
		
		# Update the internal representation with separated country code and mobile number
		self.initial_data.update({
			'country_code': country_code,
			'mobile': mobile_number
		})
		
		return mobile_number
	
	def validate(self, attrs):
		"""
		Automatically set the country field based on the country_code.
		"""
		# Get the country_code from the validated data
		country_code = attrs.get('country_code')
		
		# If no country_code is provided, try to get it from the instance or use default
		if not country_code:
			if hasattr(self, 'instance') and self.instance and self.instance.country_code:
				country_code = self.instance.country_code
			else:
				country_code = '+254'  # Default
		
		# Automatically set the country field based on country_code
		attrs['country'] = get_country_from_country_code(country_code)
		
		return attrs
	
	def to_representation(self, instance):
		"""
		Customize the representation to include documents and address.
		"""
		representation = super().to_representation(instance)
		representation['documents'] = DocumentSerializer(instance.documents.all(), many=True, context=self.context).data
		representation['address'] = AddressSerializer(instance.address, context=self.context).data if hasattr(instance, 'address') else None
		return representation