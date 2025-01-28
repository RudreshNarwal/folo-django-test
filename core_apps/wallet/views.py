# views.py
from django.core.mail import send_mail
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
import logging
import uuid
from django.conf import settings

from core_apps.users.models.user import User, Document, Address
from .models import CustomerProfile, ProviderDocument, Wallet, WalletType
from .serializers import WalletResponseSerializer
from .services.dtb_services import (
	DTBService,
	DTBServiceError,
	DTBServiceAuthenticationError,
	DTBServiceAPIError,
)
from ..users.utils import get_base64_from_s3

logger = logging.getLogger(__name__)

# Constants for mapping gender & marital status
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

RELEVANT_KYC_CHECKS = [
	"firstNameMatchesNationalIdentity",
	"identityNumberMatchesNationalIdentity",
	"lastNameMatchesNationalIdentity",
	"selfieIsASelfie",
	"selfieIsLegitimate",
	"selfieMatchesNationalIdentity",
	"matchCheck",
	"nationalIdentityIsLegitimate",
	"iprsCheck",
	"customListKycCheck",
	"internalBlackListCheck",
	"ukCheck",
	"ofacCheck",
	"unCheck",
	"dateOfBirthMatchesNationalIdentity",
	"euCheck"  # Ensure this check exists in the response
]


def handle_provider_exception(customer_profile, stage, error):
	"""
	Centralized handler for provider (DTB) exceptions during KYC.
	Sets the customer_profile as failed, saves the error, and returns an error response.
	"""
	logger.error(f"Error during {stage}: {error}")
	customer_profile.kyc_status = 'FAILED'
	customer_profile.kyc_error_message = f"{stage} Error: {str(error)}"
	customer_profile.save()
	
	return Response(
		{
			"message": f"Registration failed at {stage} stage",
			"error": str(error)
		},
		status=status.HTTP_500_INTERNAL_SERVER_ERROR
	)


class FinalizeRegistrationAPIView(APIView):
	"""
	Finalize Registration: Register with DTB API
	"""
	permission_classes = [IsAuthenticated]
	
	# @transaction.atomic
	def post(self, request):
		user = request.user
		
		# Get or create the CustomerProfile
		customer_profile, _ = CustomerProfile.objects.get_or_create(user=user)
		if not customer_profile.external_unique_id:
			customer_profile.external_unique_id = uuid.uuid4()
			customer_profile.save()
		
		kyc_service = DTBService()
		
		try:
			# ---------------------------
			# Check for Existing Customer Locally
			# ---------------------------
			if customer_profile.customer_id:
				logger.info(f"Customer ID {customer_profile.customer_id} already exists locally. Skipping external check.")
			else:
				# ---------------------------
				# Check for Existing Customer Externally
				# ---------------------------
				logger.info("Checking for existing customer in DTB system.")
				
				try:
					existing_customers = kyc_service.search_customers(user.nation_id)
				except (DTBServiceAuthenticationError, DTBServiceAPIError, DTBServiceError) as e:
					return handle_provider_exception(customer_profile, 'Existing Customer Check', e)
				
				if existing_customers:
					# Assuming the first customer in the list is the relevant one
					existing_customer = existing_customers[0]
					customer_profile.customer_id = existing_customer.get('customerId')
					customer_profile.kyc_status = 'APPROVED'  # Adjust based on actual data
					customer_profile.save()
					logger.info(f"Existing customer found with ID: {customer_profile.customer_id}. Skipping registration.")
				else:
					logger.info("No existing customer found. Proceeding with registration.")
			
			# ---------------------------
			# 1. Customer Registration (if needed)
			# ---------------------------
			if not customer_profile.customer_id:
				customer_profile.kyc_failure_stage = 'Customer Registration'
				customer_profile.save()
				
				customer_data = {
					"dateOfBirth": user.dob.strftime('%Y%m%d') if user.dob else None,
					"externalUniqueId": str(customer_profile.external_unique_id),
					"firstName": user.first_name,
					"lastName": user.last_name,
					"locale": "EN",
					"phone1": f"{user.country_code.replace('+', '')}{user.mobile}",
					"status": "ACTIVE",
					"gender": GENDER_MAPPING.get(user.gender.upper()) if user.gender else None,
					"maritalStatus": MARITAL_STATUS_MAPPING.get(user.marital_status.upper()) if user.marital_status else None,
					"birthCountry": user.country.code if user.country else None,
					"birthCity": user.city,
					"nationalIdentityNumber": user.nation_id,
					"title": (user.title or "Mr").replace(".", "").upper()
				}
				print(GENDER_MAPPING.get(user.gender.upper()))
				print(MARITAL_STATUS_MAPPING.get(user.marital_status.upper()))
				print((user.title or "Mr").replace(".", "").upper())
				
				# Validate required fields
				missing_fields = [key for key, value in customer_data.items() if value is None]
				if missing_fields:
					error_message = f"Missing required fields for registration: {', '.join(missing_fields)}"
					logger.error(error_message)
					customer_profile.kyc_status = 'FAILED'
					customer_profile.kyc_failure_stage = 'Customer Registration'
					customer_profile.kyc_error_message = error_message
					customer_profile.save()
					return Response({
						"message": "Registration failed",
						"error": error_message
					}, status=status.HTTP_400_BAD_REQUEST)
				
				try:
					kyc_response = kyc_service.register_customer(customer_data)
					customer_profile.customer_id = kyc_response.get('customerId')
					customer_profile.save()
					logger.info(f"Customer registered with ID: {customer_profile.customer_id}")
				except (DTBServiceAuthenticationError, DTBServiceAPIError, DTBServiceError) as e:
					return handle_provider_exception(customer_profile, 'Customer Registration', e)
			
			# ---------------------------
			# 2. Document Upload
			# ---------------------------
			customer_profile.kyc_failure_stage = 'Document Upload'
			customer_profile.save()
			
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
					doc_response = kyc_service.add_document(
						customer_profile.customer_id,
						document_data
					)
					ProviderDocument.objects.update_or_create(
						document=doc,
						defaults={'provider_document_id': doc_response.get('documentId')}
					)
				except (DTBServiceAuthenticationError, DTBServiceAPIError, DTBServiceError) as e:
					return handle_provider_exception(customer_profile, 'Document Upload', e)
			
			# ---------------------------
			# 3. Address Addition
			# ---------------------------
			# customer_profile.kyc_failure_stage = 'Address Addition'
			# customer_profile.save()
			#
			# try:
			#     address = Address.objects.get(user=user)
			#     address_data = {
			#         "addressType": address.address_type,
			#         "city": address.city,
			#         "country": address.country.code,
			#         "line1": address.line1,
			#         "line2": address.line2,
			#         "state": address.state,
			#         "code": address.code
			#     }
			#     try:
			#         kyc_service.add_address(customer_profile.customer_id, address_data)
			#     except (DTBServiceAuthenticationError, DTBServiceAPIError, DTBServiceError) as e:
			#         return handle_provider_exception(customer_profile, 'Address Addition', e)
			# except Address.DoesNotExist:
			#     logger.warning(f"No address found for user {user.id}. Skipping address addition to KYC.")
			
			# ---------------------------
			# 4. KYC Ratification
			# ---------------------------
			customer_profile.kyc_failure_stage = 'KYC Ratification'
			customer_profile.save()
			
			try:
				kyc_result = kyc_service.ratify_kyc(customer_profile.customer_id)
				
				# Extract relevant checks
				passed_checks = []
				failed_checks = []
				
				for check_name in RELEVANT_KYC_CHECKS:
					check = kyc_result.get(check_name)
					if check and isinstance(check, dict) and check.get('checked', False):
						if check.get('passed', False):
							passed_checks.append(check_name)
						else:
							failed_checks.append(check_name)
				
				# Determine overall KYC status
				kyc_passed = len(failed_checks) == 0
				
				if kyc_passed:
					customer_profile.kyc_status = 'APPROVED'
					customer_profile.kyc_failure_stage = None
					customer_profile.kyc_error_message = None
				else:
					customer_profile.kyc_status = 'FAILED'
					customer_profile.kyc_failure_stage = 'KYC Ratification'
					customer_profile.kyc_error_message = f"One or more KYC checks failed. Failed at {failed_checks}"
				
				customer_profile.save()
				
				if kyc_passed:
					return Response({
						"message": "Registration and KYC completed successfully.",
						"kyc_status": customer_profile.kyc_status,
						"passed_checks": passed_checks
					}, status=status.HTTP_200_OK)
				else:
					send_mail(
						subject="Error: KYC RATIFICATION FAILED",
						message=f"Failed to create wallet for customer ID {customer_profile.customer_id} as no allowed wallet type was found. Failed at {failed_checks}",
						from_email=settings.DEFAULT_FROM_EMAIL,
						recipient_list=settings.DEFAULT_EMAIL_RECEIVERS,
						fail_silently=False,
					)
					return Response({
						"message": "KYC failed.",
						"kyc_status": customer_profile.kyc_status,
						"failed_checks": failed_checks
					}, status=status.HTTP_400_BAD_REQUEST)
			
			except (DTBServiceAuthenticationError, DTBServiceAPIError, DTBServiceError) as e:
				return handle_provider_exception(customer_profile, 'KYC Ratification', e)
		
		
		except Exception as e:
			logger.error(f"Unexpected error during KYC registration: {e}")
			customer_profile.kyc_status = 'FAILED'
			customer_profile.kyc_failure_stage = 'Registration/KYC'
			customer_profile.kyc_error_message = str(e)
			customer_profile.save()
			return Response({
				"message": "Registration failed",
				"error": str(e)
			}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# New View for Creating a Customer Wallet

class CreateCustomerWalletAPIView(APIView):
	"""
	Create Customer Wallet: Automatically selects an allowed wallet type,
	creates the wallet via DTB API, and updates the local database.
	"""
	permission_classes = [IsAuthenticated]
	
	@transaction.atomic
	def post(self, request):
		user = request.user
		
		# Get the customer's profile
		try:
			customer_profile = user.customer_profile
		except CustomerProfile.DoesNotExist:
			return Response({
				"message": "Customer profile does not exist.",
				"error": "Customer profile is required to create a wallet."
			}, status=status.HTTP_400_BAD_REQUEST)
		
		# Ensure customer_id is present
		if not customer_profile.customer_id:
			return Response({
				"message": "Customer is not registered with DTB.",
				"error": "Please complete registration and KYC first."
			}, status=status.HTTP_400_BAD_REQUEST)
		
		kyc_service = DTBService()
		
		try:
			# ---------------------------
			# Fetch Allowed Wallet Types
			# ---------------------------
			logger.info("Fetching allowed wallet types from DTB.")
			wallet_types_response = kyc_service.get_wallet_types()
			wallet_types = wallet_types_response  # Assuming response is a list of dicts
			
			# Sort wallet types by walletTypeId descending to prioritize higher IDs
			sorted_wallet_types = sorted(wallet_types, key=lambda x: x.get('walletTypeId', 0), reverse=True)
			
			# Select the first allowed walletTypeId
			selected_wallet_type_id = 2497
			# for wallet_type in sorted_wallet_types:
			#     if wallet_type.get('allowed', False):
			#         selected_wallet_type_id = wallet_type.get('walletTypeId')
			#         logger.info(f"Selected walletTypeId: {selected_wallet_type_id} as it is allowed.")
			#         break
			
			if not selected_wallet_type_id:
				# No allowed wallet type found
				error_message = "No allowed wallet type found for the customer."
				logger.error(error_message)
				# Trigger an email notification
				send_mail(
					subject="Error: Wallet Creation Failed",
					message=f"Failed to create wallet for customer ID {customer_profile.customer_id} as no allowed wallet type was found.",
					from_email=settings.DEFAULT_FROM_EMAIL,
					recipient_list=settings.DEFAULT_EMAIL_RECEIVERS,
					fail_silently=False,
				)
				
				return Response({
					"message": "Wallet creation failed.",
					"error": error_message
				}, status=status.HTTP_400_BAD_REQUEST)
			
			# ---------------------------
			# Create Wallet JSON Payload
			# ---------------------------
			wallet_payload = {
				"externalUniqueId": str(uuid.uuid4()),
				"status": "ACTIVE",
				"name": "Cust DTB Wallet",
				"description": "Cust DTB Wallet",
				"walletTypeId": selected_wallet_type_id,
				"cardType": "virtual",
				"configuration": []
			}
			
			logger.debug(f"Wallet payload for creation: {wallet_payload}")
			
			# ---------------------------
			# Create Wallet via DTB API
			# ---------------------------
			wallet_response = kyc_service.create_wallet(customer_profile.customer_id, wallet_payload)
			logger.info(f"Wallet created with externalUniqueId: {wallet_response.get('externalUniqueId')}")
			
			# ---------------------------
			# Update Database
			# ---------------------------
			# Get or create the WalletType
			wallet_type_id = wallet_response.get('walletTypeId')
			try:
				wallet_type = WalletType.objects.get(wallet_type_id=wallet_type_id)
			except WalletType.DoesNotExist:
				# Optionally, handle the case where WalletType does not exist locally
				return Response({
					"message": "Invalid wallet type returned from DTB.",
					"error": f"WalletType with ID {wallet_type_id} does not exist locally."
				}, status=status.HTTP_400_BAD_REQUEST)
			
			# Create the Wallet instance
			wallet = Wallet.objects.create(
				user=user,
				external_unique_id=uuid.UUID(wallet_response.get('externalUniqueId')),
				wallet_id=wallet_response.get('walletId'),
				wallet_type=wallet_type,
				name=wallet_response.get('name'),
				description=wallet_response.get('description'),
				card_type=wallet_response.get('cardType'),
				status=wallet_response.get('status'),
				currency=wallet_response.get('currency'),
				available_balance=wallet_response.get('availableBalance'),
				current_balance=wallet_response.get('currentBalance'),
				reservations=wallet_response.get('reservations'),
				account_number=wallet_response.get('accountNumber'),
				friendly_id=wallet_response.get('friendlyId'),
				customer=customer_profile,
				organisation_id=wallet_response.get('organisationId'),
				configuration=wallet_response.get('configuration')
			)
			
			logger.info(f"Wallet {wallet.id} created locally for user {user.id}.")
			
			# Serialize the wallet data for response
			response_serializer = WalletResponseSerializer(wallet)
			
			return Response({
				"message": "Wallet created successfully.",
				"wallet": response_serializer.data
			}, status=status.HTTP_201_CREATED)
		
		except (DTBServiceAuthenticationError, DTBServiceAPIError, DTBServiceError) as e:
			return handle_provider_exception(customer_profile, 'Create Wallet', e)
		except Exception as e:
			logger.error(f"Unexpected error during wallet creation: {e}")
			return Response({
				"message": "Wallet creation failed.",
				"error": str(e)
			}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
