from __future__ import unicode_literals

import json
import requests
from rest_framework import generics, status, response
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from core_apps.users.models.user import User
from core_apps.users.serializers.auth import VerifyOTPRequestSerializer
from django.contrib.auth import get_user_model
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from django_countries.serializer_fields import CountryField
from phonenumber_field.serializerfields import PhoneNumberField
from rest_framework import serializers
from django_countries.serializer_fields import CountryField
from ..models.user import User, Document, Address, UserTask
from ..utils import upload_to_s3, generate_presigned_url
import base64
from django.core.files.base import ContentFile
from django.db import transaction
from rest_framework.decorators import action
import uuid
import logging
from rest_framework.views import APIView
from celery.result import AsyncResult

from ..services.id_analysis import IDAnalysisService
from ..tasks import analyze_id_images

logger = logging.getLogger(__name__)


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
	
	def to_representation(self, instance):
		"""
		Customize the representation to include documents and address.
		"""
		representation = super().to_representation(instance)
		representation['documents'] = DocumentSerializer(instance.documents.all(), many=True, context=self.context).data
		representation['address'] = AddressSerializer(instance.address, context=self.context).data if hasattr(instance, 'address') else None
		return representation


class IsOwnerOrReadOnly(IsAuthenticated):
	# Custom permission to only allow owners of an object to edit it. Assumes the model instance has an `owner` attribute.
	def has_object_permission(self, request, view, obj):
		# Read permissions are allowed to any request, so we'll always allow GET, HEAD or OPTIONS requests.
		# if request.method in ('GET', 'HEAD', 'OPTIONS'):
		#     return True
		# Write permissions are only allowed to the owner of the user profile.
		return obj == request.user


class UserViewSet(viewsets.ModelViewSet):
	# A viewset for viewing and editing the logged in user's profile.
	queryset = User.objects.all()
	serializer_class = UserSerializer
	permission_classes = [IsOwnerOrReadOnly]
	
	def get_object(self):
		# Overrides the default method to return the user profile for the logged in user.
		# Ensure the user is trying to get or update their own profile
		# This is useful for URLs like /api/users/me/ where `me` can be used
		# as a keyword to get the logged-in user's profile.
		if self.kwargs.get('pk', None) == 'me':
			return self.request.user
		return super(UserViewSet, self).get_object()
	
	def partial_update(self, request, *args, **kwargs):
		# Custom update method to handle user profile updates.
		instance = self.get_object()
		# Prevent users from updating other users' profiles
		if instance != request.user:
			return Response(
				{'message': 'You do not have permission to update this user.'},
				status=status.HTTP_403_FORBIDDEN
			)
		# Extract address data if present
		address_data = request.data.pop('address', None)
		# Update user data
		serializer = self.get_serializer(
			instance, data=request.data, partial=kwargs.pop('partial', True)
		)
		serializer.is_valid(raise_exception=True)
		self.perform_update(serializer)
		# Update or create address if address data is provided
		if address_data:
			address_instance = getattr(instance, 'address', None)
			address_serializer = AddressSerializer(
				address_instance, data=address_data, partial=True
			)
			address_serializer.is_valid(raise_exception=True)
			address_serializer.save(user=instance)
		# Prepare response data
		response_data = serializer.data
		response_data['address'] = AddressSerializer(
			instance.address, context=self.get_serializer_context()
		).data if hasattr(instance, 'address') else None
		
		return Response(response_data)
	
	@action(methods=['GET'], detail=False)
	def me(self, request):
		user = request.user
		serializer = UserSerializer(instance=user)
		return response.Response(serializer.data)
	
	@action(detail=False, methods=['post'])
	def register(self, request, *args, **kwargs):
		# Check if the user already exists
		if request.user.email is not None:
			return response.Response({
				"message": "User already registered."
			}, status=status.HTTP_400_BAD_REQUEST)
		
		serializer = self.get_serializer(request.user, data=request.data, partial=kwargs.pop('partial', True))
		serializer.is_valid(raise_exception=True)
		self.perform_update(serializer)
		
		# Return the newly registered user's data
		return response.Response({
			"user": serializer.data,
			"message": "User successfully registered."
		}, status=status.HTTP_201_CREATED)
	
	def update(self, request, *args, **kwargs):
		# Disable the partial update (PUT) action.
		return Response({'message': 'PUT method is not allowed.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
	
	def list(self, request, *args, **kwargs):
		# Disable the partial update (PATCH) action.
		return Response({'message': 'GET list method is not allowed.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
	
	def destroy(self, request, *args, **kwargs):
		# Disable the destroy (DELETE) action.
		return Response({'message': 'DELETE method is not allowed.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)


class UploadDocumentAPIView(generics.CreateAPIView):
	"""
	On Boarding Step 3: Upload Documents
	"""
	serializer_class = DocumentSerializer
	permission_classes = [IsAuthenticated]
	
	def get_queryset(self):
		return Document.objects.filter(user=self.request.user)
	
	@transaction.atomic
	def post(self, request, *args, **kwargs):
		serializer = self.get_serializer(data=request.data, context={'request': request})
		try:
			serializer.is_valid(raise_exception=True)
			document = serializer.save()
			return Response({
				"status": "success",
				"message": "Document uploaded successfully.",
				"data": DocumentSerializer(document, context={'request': request}).data
			}, status=status.HTTP_201_CREATED)
		except serializer.ValidationError as ve:
			logger.error(f"Validation error during document upload: {ve}")
			return Response({
				"status": "error",
				"message": "Document upload failed.",
				"errors": ve.detail
			}, status=status.HTTP_400_BAD_REQUEST)
		except Exception as e:
			logger.error(f"Unexpected error during document upload: {e}")
			return Response({
				"status": "error",
				"message": "An unexpected error occurred during document upload.",
				"errors": str(e)
			}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Not in use right now for future use only. We are using UserSerializer partial_update
class SaveAddressAPIView(generics.UpdateAPIView):
	"""
	Onboarding Step 4: Provide Address
	"""
	serializer_class = AddressSerializer
	permission_classes = [IsAuthenticated]
	
	def get_object(self):
		return self.request.user.address if hasattr(self.request.user, 'address') else None
	
	@transaction.atomic
	def post(self, request, *args, **kwargs):
		user = self.request.user
		address_instance = self.get_object()
		serializer = self.get_serializer(address_instance, data=request.data, partial=True)
		try:
			serializer.is_valid(raise_exception=True)
			serializer.save(user=user)
			return Response({
				"status": "success",
				"message": "Address saved successfully.",
				"data": serializer.data
			}, status=status.HTTP_200_OK if address_instance else status.HTTP_201_CREATED)
		except serializer.ValidationError as ve:
			logger.error(f"Validation error during address save: {ve}")
			return Response({
				"status": "error",
				"message": "Address save failed.",
				"errors": ve.detail
			}, status=status.HTTP_400_BAD_REQUEST)
		except Exception as e:
			logger.error(f"Unexpected error during address save: {e}")
			return Response({
				"status": "error",
				"message": "An unexpected error occurred during address save.",
				"errors": str(e)
			}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AnalyzeIDView(APIView):
	"""
	Asynchronous endpoint that creates a task for ID analysis.
	Use this in production for better user experience.
	"""
	permission_classes = [IsAuthenticated]
	
	def post(self, request):
		try:
			# Check if the task already exists and is completed
			existing_task = UserTask.objects.filter(
				user=request.user,
				task_type='NATIONAL_ID_DATA_EXTRACTION',
				status='COMPLETED'
			).first()
			
			if existing_task and request.user.nation_id:  # Check both if task exists and nation_id is not empty
				# If the task is already completed and the nation_id is not null or empty, return success response
				return Response({
					"message": "ID analysis has already been completed.",
					"task_id": existing_task.task_id,
					"status": "completed"
				}, status=status.HTTP_200_OK)
			
			# Get documents using service
			front_doc, back_doc = IDAnalysisService.get_id_documents(request.user)
			
			# Check if S3 keys are present
			if not front_doc.s3_key or not back_doc.s3_key:
				return Response({
					"message": "Missing S3 key for front and/or back document."
				}, status=status.HTTP_404_NOT_FOUND)
			
			# Create UserTask instance first
			task_id = str(uuid.uuid4())
			user_task = UserTask.objects.create(
				user=request.user,
				task_id=task_id,
				task_type='NATIONAL_ID_DATA_EXTRACTION',
				status='PROCESSING'
			)
			
			# Launch Celery task with task_id and S3 keys
			celery_task = analyze_id_images.delay(
				task_id,
				front_doc.s3_key,
				back_doc.s3_key
			)
			
			return Response({
				"message": "ID analysis task scheduled.",
				"task_id": task_id,
				"status": "processing"
			}, status=status.HTTP_202_ACCEPTED)
		
		except Document.DoesNotExist:
			return Response({
				"message": "Required front/back ID documents not found."
			}, status=status.HTTP_404_NOT_FOUND)
		
		except Exception as e:
			logger.error(f"Error initiating ID analysis: {str(e)}")
			return Response({
				"message": "Error initiating analysis",
				"error": str(e)
			}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TestAnalyzeIDView(APIView):
	"""
	Synchronous endpoint for testing ID analysis.
	Use this only for testing purposes as it may timeout for long-running analyses.
	"""
	permission_classes = [IsAuthenticated]
	
	def post(self, request):
		try:
			# Check if the task already exists and is completed
			existing_task = UserTask.objects.filter(
				user=request.user,
				task_type='NATIONAL_ID_DATA_EXTRACTION',
				status='COMPLETED'
			).first()
			
			if existing_task and request.user.nation_id:  # Check both if task exists and nation_id is not empty
				# If the task is already completed and the nation_id is not null or empty, return success response
				return Response({
					"message": "ID analysis has already been completed.",
					"task_id": existing_task.task_id,
					"status": "completed"
				}, status=status.HTTP_200_OK)
			
			# Get documents using service
			front_doc, back_doc = IDAnalysisService.get_id_documents(request.user)
			
			# Analyze images using service
			extracted_data = IDAnalysisService.analyze_id_images(
				front_doc.s3_key,
				back_doc.s3_key
			)
			
			# Update user data using service
			IDAnalysisService.update_user_data(request.user, extracted_data)

			return Response({
				"message": "ID analysis completed successfully",
				"data": extracted_data.dict()
			}, status=status.HTTP_200_OK)

		except Document.DoesNotExist:
			return Response({
				"message": "Required front/back ID documents not found."
			}, status=status.HTTP_404_NOT_FOUND)
			
		except ValueError as e:
			return Response({
				"message": str(e)
			}, status=status.HTTP_400_BAD_REQUEST)
			
		except json.JSONDecodeError as e:
			logger.error(f"Error parsing OpenAI response: {str(e)}")
			return Response({
				"message": "Error parsing ID data",
				"error": str(e)
			}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
			
		except Exception as e:
			logger.error(f"Error analyzing ID: {str(e)}")
			return Response({
				"message": "Error analyzing ID",
				"error": str(e)
			}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CheckAnalysisStatus(APIView):
	permission_classes = [IsAuthenticated]
	
	def get(self, request, task_id):
		try:
			# Get the task from UserTask model
			user_task = UserTask.objects.get(
				task_id=task_id,
				user=request.user  # Ensure user can only check their own tasks
			)
			
			response_data = {
				"task_id": task_id,
				"status": user_task.status,
				"started_at": user_task.started_at,
				"completed_at": user_task.completed_at,
				"task_type": user_task.task_type
			}
			
			# Add result or error message based on status
			if user_task.status == 'COMPLETED':
				response_data["result"] = user_task.result
			elif user_task.status == 'FAILED':
				response_data["error"] = user_task.error_message
			
			return Response(response_data)
		
		except UserTask.DoesNotExist:
			return Response({
				"message": "Task not found or you don't have permission to view it"
			}, status=status.HTTP_404_NOT_FOUND)
		
		except Exception as e:
			logger.error(f"Error checking task status: {str(e)}")
			return Response({
				"message": "Error checking task status",
				"error": str(e)
			}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)