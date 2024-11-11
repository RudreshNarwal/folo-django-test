# views.py

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from core_apps.users.models.user import User, Document, Address
from .models import CustomerProfile, ProviderDocument
from .services.dtb_services import DTBService, DTBServiceError, DTBServiceAuthenticationError, DTBServiceAPIError
from ..users.utils import get_base64_from_s3
from django.db import transaction
import logging
import uuid

logger = logging.getLogger(__name__)


class FinalizeRegistrationAPIView(APIView):
	"""
	Finalize Registration: Register with DTB API
	"""
	permission_classes = [IsAuthenticated]
	
	@transaction.atomic
	def post(self, request):
		user = request.user
		# Get or create the customer profile
		customer_profile, created = CustomerProfile.objects.get_or_create(user=user)
		if not customer_profile.external_unique_id:
			customer_profile.external_unique_id = uuid.uuid4()
			customer_profile.save()
		
		kyc_service = DTBService()
		try:
			# Authentication is handled in DTBService __init__
			GENDER_MAPPING = {
				"MALE": "M",
				"FEMALE": "F",
				"OTHER": "O"
			}
			MARITAL_STATUS_MAPPING = {
				"SINGLE": "S",
				"MARRIED": "M",
				"DIVORCED": "D",
				"WIDOWED": "W"
			}
			
			# Prepare customer data
			customer_data = {
				"dateOfBirth": user.dob.strftime('%Y%m%d'),
				"externalUniqueId": str(customer_profile.external_unique_id),
				"firstName": user.first_name,
				"lastName": user.last_name,
				"locale": "EN",
				"phone1": f"{user.country_code.replace('+', '')}{user.mobile}",
				"status": "ACTIVE",
				"gender": GENDER_MAPPING.get(user.gender.upper()),
				"maritalStatus": MARITAL_STATUS_MAPPING.get(user.marital_status.upper()),
				"birthCountry": user.country.code,
				"birthCity": user.city,
				"nationalIdentityNumber": user.nation_id,
				"title": (user.title or "Mr.").replace(".", "").upper()
			}
			
			# Before customer registration
			customer_profile.kyc_failure_stage = 'Customer Registration'
			customer_profile.save()
			
			# Register customer with KYC provider
			try:
				kyc_response = kyc_service.register_customer(customer_data)
				customer_profile.provider_customer_id = kyc_response.get('customerId')
				customer_profile.save()
			except (DTBServiceAuthenticationError, DTBServiceAPIError, DTBServiceError) as e:
				logger.error(f"Error during customer registration: {e}")
				# Handle fallback scenario
				customer_profile.kyc_status = 'FAILED'
				customer_profile.kyc_error_message = f"Customer Registration Error: {str(e)}"
				customer_profile.save()
				return Response({
					"message": "Registration failed at Customer Registration stage",
					"error": str(e)
				}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
			
			# Before document upload
			customer_profile.kyc_failure_stage = 'Document Upload'
			customer_profile.save()
			
			# Upload documents to KYC provider
			documents = Document.objects.filter(
				user=user,
				document_type__in=['NATIONAL_IDENTITY', 'FACIAL_PHOTO']
			)
			for doc in documents:
				base64_encoded_document = get_base64_from_s3(doc.s3_key)
				document_data = {
					"base64EncodedDocument": base64_encoded_document,
					"documentType": doc.document_type,
					"mediaType": doc.media_type
				}
				try:
					doc_response = kyc_service.add_document(customer_profile.provider_customer_id, document_data)
					# Save provider_document_id in wallet app
					ProviderDocument.objects.create(
						document=doc,
						provider_document_id=doc_response.get('documentId')
					)
				except (DTBServiceAuthenticationError, DTBServiceAPIError, DTBServiceError) as e:
					logger.error(f"Error during document upload: {e}")
					# Handle fallback scenario
					customer_profile.kyc_status = 'FAILED'
					customer_profile.kyc_error_message = f"Document Upload Error: {str(e)}"
					customer_profile.save()
					return Response({
						"message": "Registration failed at Document Upload stage",
						"error": str(e)
					}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
			
			# Before address addition
			customer_profile.kyc_failure_stage = 'Address Addition'
			customer_profile.save()
			
			# Add address to KYC provider
			try:
				address = Address.objects.get(user=user)
				address_data = {
					"addressType": address.address_type,
					"city": address.city,
					"country": address.country.code,
					"line1": address.line1,
					"line2": address.line2,
					"state": address.state,
					"code": address.code
				}
				try:
					kyc_service.add_address(customer_profile.provider_customer_id, address_data)
				except (DTBServiceAuthenticationError, DTBServiceAPIError, DTBServiceError) as e:
					logger.error(f"Error during address addition: {e}")
					# Handle fallback scenario
					customer_profile.kyc_status = 'FAILED'
					customer_profile.kyc_error_message = f"Address Addition Error: {str(e)}"
					customer_profile.save()
					return Response({
						"message": "Registration failed at Address Addition stage",
						"error": str(e)
					}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
			except Address.DoesNotExist:
				logger.warning(f"No address found for user {user.id}. Skipping address addition to KYC.")
			
			# Before KYC ratification
			customer_profile.kyc_failure_stage = 'KYC Ratification'
			customer_profile.save()
			
			# Ratify KYC
			try:
				kyc_result = kyc_service.ratify_kyc(customer_profile.provider_customer_id)
				# Process KYC response and update status
				kyc_passed = all(
					check.get('passed', False)
					for check in kyc_result.values()
					if isinstance(check, dict) and check.get('checked', False)
				)
				customer_profile.kyc_status = 'APPROVED' if kyc_passed else 'FAILED'
				customer_profile.kyc_failure_stage = None  # Reset failure stage on success
				customer_profile.kyc_error_message = None if kyc_passed else 'Customer is not ratified' # Clear error message
				customer_profile.save()
			except (DTBServiceAuthenticationError, DTBServiceAPIError, DTBServiceError) as e:
				logger.error(f"Error during KYC ratification: {e}")
				# Handle fallback scenario
				customer_profile.kyc_status = 'FAILED'
				customer_profile.kyc_error_message = f"KYC Ratification Error: {str(e)}"
				customer_profile.save()
				return Response({
					"message": "Registration failed at KYC Ratification stage",
					"error": str(e)
				}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
			
			return Response({
				"message": "Registration and KYC completed",
				"kyc_status": customer_profile.kyc_status
			}, status=status.HTTP_200_OK)
		
		except Exception as e:
			logger.error(f"Unexpected error during KYC registration: {e}")
			# Handle fallback scenario
			customer_profile.kyc_status = 'FAILED'
			customer_profile.kyc_failure_stage = 'Registration/KYC'
			customer_profile.kyc_error_message = str(e)
			customer_profile.save()
			return Response({
				"message": "Registration failed",
				"error": str(e)
			}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
