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
from ..serializers.user import (
	DocumentSerializer,
	AddressSerializer
)
from ..models.user import Document, Address, UserTask
from django.db import transaction
from rest_framework.decorators import action
import uuid
import logging
from rest_framework.views import APIView
from celery.result import AsyncResult
from ..tasks import analyze_id_images

logger = logging.getLogger(__name__)

from ..serializers.user import UserSerializer


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


## Not in use right now for future use only. We are using UserSerializer partial_update
class SaveAddressAPIView(generics.UpdateAPIView):
	"""
	On Boarding Step 4: Provide Address
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
			
			# Attempt to get both front and back ID documents
			front_doc = Document.objects.get(
				user=request.user,
				document_type='NATIONAL_IDENTITY'
			)
			back_doc = Document.objects.get(
				user=request.user,
				document_type='NATIONAL_IDENTITY_BACK'
			)
			
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
