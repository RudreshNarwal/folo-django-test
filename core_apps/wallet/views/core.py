# views.py
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.pagination import PageNumberPagination
from django.db import transaction
import logging
import uuid
from django.conf import settings
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from django.db.models import Q

from core_apps.users.models.user import User, Document, Address
from ..models import CardType, CustomerProfile, ProviderDocument, TopUpTransaction, Wallet, WalletType, Transaction
from ..serializers import TopUpTransactionSerializer, WalletDetailsSerializer, WalletResponseSerializer, WalletSerializer
from ..services.dtb_services import (
	DTBService,
	DTBServiceError,
	DTBServiceAuthenticationError,
	DTBServiceAPIError,
)
from core_apps.users.utils import get_base64_from_s3
from ..services.wallet_service import create_wallet_for_customer, WalletCreationError
from core_apps.common.services.email_service import EmailService

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
	
	# Send KYC review email to user
	if customer_profile.user.email:
		try:
			EmailService.send_kyc_review_email(customer_profile.user)
		except Exception as e:
			logger.error(f"Failed to send KYC review email to {customer_profile.user.email}: {e}")
	
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
					# "maritalStatus": MARITAL_STATUS_MAPPING.get(user.marital_status.upper()) if user.marital_status else None,
					"birthCountry": user.country.code if user.country else None,
					"birthCity": user.district_of_birth,
					"nationalIdentityNumber": user.nation_id,
					"title": (user.title or "Mr").replace(".", "").upper()
				}
				
				# Validate required fields
				missing_fields = [key for key, value in customer_data.items() if value is None]
				if missing_fields:
					error_message = f"Missing required fields for registration: {', '.join(missing_fields)}"
					logger.error(error_message)
					customer_profile.kyc_status = 'FAILED'
					customer_profile.kyc_failure_stage = 'Customer Registration'
					customer_profile.kyc_error_message = error_message
					customer_profile.save()

					# Send KYC review email
					if user.email:
						try:
							EmailService.send_kyc_review_email(user)
						except Exception as e:
							logger.error(f"Failed to send KYC review email to {user.email}: {e}")

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
				document_type__in=['NATIONAL_IDENTITY', 'FACIAL_PHOTO', 'BACK_OF_NATIONAL_IDENTITY']
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
					# Send KYC review email
					if user.email:
						try:
							EmailService.send_kyc_review_email(user)
						except Exception as e:
							logger.error(f"Failed to send KYC review email to {user.email}: {e}")
							
					send_mail(
						subject="Error: KYC RATIFICATION FAILED",
						message=f"Failed to create wallet for customer ID {customer_profile.customer_id} as no allowed wallet type was found. Failed at {failed_checks}",
						from_email=settings.DEFAULT_FROM_EMAIL,
						recipient_list=settings.DEFAULT_EMAIL_RECEIVERS,
						fail_silently=False,
					)
					return Response({
						"message": f"KYC failed. Failed at {customer_profile.kyc_status}. Failed Check {failed_checks}",
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

			# Send KYC review email
			if user.email:
				try:
					EmailService.send_kyc_review_email(user)
				except Exception as email_exc:
					logger.error(f"Failed to send KYC review email to {user.email}: {email_exc}")

			return Response({
				"message": "Registration failed",
				"error": str(e)
			}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# New View for Creating a Customer Wallet

class CreateCustomerWalletAPIView(APIView):
	"""
	Create Customer Wallet: Creates a wallet for an approved customer.
	This can be called manually if the automatic process fails.
	"""
	permission_classes = [IsAuthenticated]
	
	@transaction.atomic
	def post(self, request):
		user = request.user
		
		try:
			customer_profile = user.customer_profile
		except CustomerProfile.DoesNotExist:
			return Response({
				"message": "Customer profile does not exist.",
				"error": "Customer profile is required to create a wallet."
			}, status=status.HTTP_400_BAD_REQUEST)
		
		try:
			wallet = create_wallet_for_customer(customer_profile)
			
			# Send wallet creation success email
			if user.email:
				try:
					EmailService.send_wallet_creation_success_email(user)
				except Exception as e:
					logger.error(f"Failed to send wallet creation success email to {user.email}: {e}")
			
			response_serializer = WalletResponseSerializer(wallet)
			return Response({
				"message": "Wallet created or already exists.",
				"wallet": response_serializer.data
			}, status=status.HTTP_201_CREATED)

		except WalletCreationError as e:
			logger.error(f"Manual wallet creation failed for user {user.id}: {e}")
			return Response({
				"message": "Wallet creation failed.",
				"error": str(e)
			}, status=status.HTTP_400_BAD_REQUEST)


class TopUpMoneyAPIView(APIView):
	permission_classes = [IsAuthenticated]
	
	def post(self, request):
		user = request.user
		try:
			wallet = Wallet.objects.get(user=user, status='ACTIVE')
		except Wallet.DoesNotExist:
			return Response({"error": "No active wallet found."}, status=status.HTTP_400_BAD_REQUEST)
		
		amount = request.data.get('amount')
		if not amount or not isinstance(amount, (int, float)) or amount < 10 or amount > 150000:
			return Response({"error": "Invalid amount. Must be between 10 and 150,000."}, status=status.HTTP_400_BAD_REQUEST)
		
		currency = request.data.get('currency', 'KES')
		phone = user.get_mobile_without_plus
		description = request.data.get('description', 'Top Up Money')
		external_unique_id = uuid.uuid4()
		callback_url = settings.ADD_MONEY_WEBHOOK_URL
		
		payload = {
			"additionalFields": [{"id": "merchantWalletId", "value": str(wallet.wallet_id)}],
			"amount": amount,
			"currency": currency,
			"externalUniqueId": str(external_unique_id),
			"callbackUrl": callback_url,
			"externalWalletId": phone,
			"phone": phone,
			"externalWalletType": "SFCM",
			"description": description,
			"type": "KE_DTB_MPESA_PROMPT"
		}
		
		kyc_service = DTBService()
		try:
			response = kyc_service.initiate_top_up(payload)
			transaction = TopUpTransaction.objects.create(
				payment_id=response['paymentId'],
				external_unique_id=external_unique_id,
				status=response['status'],
				amount=response['amount'],
				currency=response['currency'],
				description=response['description'],
				merchant_name=response['merchantName'],
				payment_type=response['paymentType'],
				created_at=response['created'],
				extra_info=response.get('extraInfo'),
				payment_instrument_info=response['paymentInstrumentInfo'],
				fee=response['fee'],
				wallet=wallet,
				customer=user.customer_profile,
			)
			return Response({
				"message": "Top-up initiated successfully.",
				"transaction": {
					"payment_id": transaction.payment_id,
					"status": transaction.status,
					"amount": float(transaction.amount),
					"currency": transaction.currency,
				}
			}, status=status.HTTP_201_CREATED)
		except DTBServiceAPIError as e:
			logger.error(f"DTB API Error during top-up: {e}")
			return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
		except Exception as e:
			logger.error(f"Unexpected error during top-up: {e}")
			return Response({"error": "An unexpected error occurred."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TopUpWebhookAPIView(APIView):
	permission_classes = []  # Allow unauthenticated access for webhook callbacks
	def post(self, request):
		data = request.data
		payment_id = data.get('paymentId')
		topup_status = data.get('status')
		error_description = data.get('errorDescription')
		
		try:
			transaction = TopUpTransaction.objects.get(payment_id=payment_id)
			transaction.status = topup_status
			if topup_status == 'ERROR_PERM':
				transaction.error_description = error_description
			transaction.payment_reference = data.get('paymentReference', '')
			transaction.gateway_transaction_id = data.get('gatewayTransactionId', '')
			transaction.save()
			
			if topup_status == 'SUCCESSFUL':
				kyc_service = DTBService()
				wallet_details = kyc_service.get_wallet_details(transaction.wallet.wallet_id)
				wallet = transaction.wallet
				wallet.available_balance = wallet_details['availableBalance']
				wallet.current_balance = wallet_details['currentBalance']
				wallet.save()
				logger.info(f"Wallet {wallet.wallet_id} balance updated successfully.")
			return Response({"message": "Webhook received and processed."}, status=status.HTTP_200_OK)
		except TopUpTransaction.DoesNotExist:
			logger.error(f"Webhook received for unknown payment_id: {payment_id}")
			return Response({"error": "Transaction not found."}, status=status.HTTP_404_NOT_FOUND)
		except Exception as e:
			logger.error(f"Error processing webhook for payment_id {payment_id}: {e}")
			return Response({"error": "An unexpected error occurred."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TopUpStatusAPIView(APIView):
	permission_classes = [IsAuthenticated]
	
	def get(self, request, wallet_id, payment_id):
		try:
			# Get top-up status from DTB service
			dtb_service = DTBService()
			status_response = dtb_service.get_top_up_status(wallet_id, payment_id)
			
			# Extract relevant data from the status response
			topup_id = status_response.get('topupId')
			topup_status = status_response.get('status')
			
			# Find the transaction using external_unique_id (which should match payment_id)
			try:
				transaction = TopUpTransaction.objects.get(payment_id=topup_id)
				# Update transaction status
				transaction.status = topup_status
				
				if topup_status == 'ERROR_PERM':
					transaction.error_description = status_response.get('description', '')
				
				transaction.gateway = status_response.get('gateway', '')
				transaction.gateway_transaction_id = status_response.get('gatewayTransactionId', '')
				transaction.save()
				
				# If transaction is successful, update the wallet balance
				if topup_status == 'SUCCESSFUL':
					wallet = transaction.wallet
					# Get updated wallet details
					wallet_details = dtb_service.get_wallet_details(wallet.wallet_id)
					wallet.available_balance = wallet_details['availableBalance']
					wallet.current_balance = wallet_details['currentBalance']
					wallet.save()
					logger.info(f"Wallet {wallet.wallet_id} balance updated successfully.")
				
				# Return relevant information in the response
				return Response(status_response)
			
			except TopUpTransaction.DoesNotExist:
				logger.error(f"No transaction found for payment_id: {payment_id}")
				return Response({
					"status": "error",
					"message": f"No transaction found for payment_id: {payment_id}"
				}, status=status.HTTP_404_NOT_FOUND)
		
		except Exception as e:
			logger.error(f"Error checking top-up status for wallet_id {wallet_id}, payment_id {payment_id}: {str(e)}")
			return Response({
				'status': 'error',
				'message': str(e)
			}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserWalletAPIView(APIView):
	permission_classes = [IsAuthenticated]
	
	def get(self, request):
		try:
			# 1. Fetch the local wallet instance
			local_wallet = Wallet.objects.select_related('user', 'customer', 'wallet_type').get(user=request.user, status='ACTIVE')
		except Wallet.DoesNotExist:
			return Response({"error": "No active wallet found for this user."}, status=status.HTTP_404_NOT_FOUND)
		except Wallet.MultipleObjectsReturned:
			# If multiple active wallets could exist (though OneToOne on user should prevent this for 'wallet_profile')
			# Prioritize or log an error. For now, let's take the first one.
			local_wallet = Wallet.objects.select_related('user', 'customer', 'wallet_type').filter(user=request.user,
			                                                                                       status='ACTIVE').first()
			if not local_wallet:  # Should not happen if MultipleObjectsReturned was raised, but as a safeguard.
				return Response({"error": "Error fetching active wallet for this user."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
		
		try:
			# 2. Fetch latest wallet details from DTB Service
			dtb_service = DTBService()
			# Assuming local_wallet.wallet_id is the correct identifier for DTB's system
			dtb_wallet_data = dtb_service.get_wallet_details(local_wallet.wallet_id)
			
			# 3. Update local_wallet instance with data from DTB
			# It's good practice to use .get() with defaults for potentially missing keys
			local_wallet.name = dtb_wallet_data.get('name', local_wallet.name)
			local_wallet.description = dtb_wallet_data.get('description', local_wallet.description)
			local_wallet.current_balance = dtb_wallet_data.get('currentBalance', local_wallet.current_balance)
			local_wallet.available_balance = dtb_wallet_data.get('availableBalance', local_wallet.available_balance)
			local_wallet.reservations = dtb_wallet_data.get('reservations', local_wallet.reservations)
			
			new_status = dtb_wallet_data.get('status', local_wallet.status)
			# Ensure the status from DTB is valid for your model's choices
			if any(new_status in choice for choice in Wallet._meta.get_field('status').choices):
				local_wallet.status = new_status
			else:
				# Log a warning if the status is not recognized, keep the old one
				logger.warning(
					f"Received unrecognized wallet status '{new_status}' from DTB for wallet ID {local_wallet.wallet_id}. Keeping old status '{local_wallet.status}'.")
			
			# Handle datetime string from DTB
			created_str = dtb_wallet_data.get('created')
			if created_str:
				parsed_created = parse_datetime(created_str)
				if parsed_created:
					local_wallet.created = parsed_created
				else:
					logger.warning(f"Could not parse 'created' datetime '{created_str}' from DTB for wallet ID {local_wallet.wallet_id}.")
			
			# Handle wallet_type_id
			dtb_wallet_type_id = dtb_wallet_data.get('walletTypeId')
			if dtb_wallet_type_id:
				try:
					wallet_type_instance = WalletType.objects.get(wallet_type_id=dtb_wallet_type_id)
					local_wallet.wallet_type = wallet_type_instance
				except WalletType.DoesNotExist:
					logger.error(f"WalletType with ID {dtb_wallet_type_id} not found in local DB for wallet {local_wallet.wallet_id}.")
				# Decide how to handle: fail, or keep old, or create new WalletType?
				# For now, we log an error and local_wallet.wallet_type remains unchanged.
			
			local_wallet.external_unique_id = dtb_wallet_data.get('externalUniqueId', local_wallet.external_unique_id)
			local_wallet.currency = dtb_wallet_data.get('currency', local_wallet.currency)
			local_wallet.friendly_id = dtb_wallet_data.get('friendlyId', local_wallet.friendly_id)
			local_wallet.account_number = dtb_wallet_data.get('accountNumber', local_wallet.account_number)
			local_wallet.configuration = dtb_wallet_data.get('configuration', local_wallet.configuration)
			
			# If DTB's customerId maps to your CustomerProfile.customer_id
			dtb_customer_id = dtb_wallet_data.get('customerId')
			if dtb_customer_id and local_wallet.customer:
				if local_wallet.customer.customer_id != dtb_customer_id:
					# This might indicate a mismatch or a need to update/relink CustomerProfile
					logger.warning(
						f"DTB customer ID {dtb_customer_id} differs from local {local_wallet.customer.customer_id} for wallet {local_wallet.wallet_id}")
					# Potentially find and link to the correct CustomerProfile or update it:
					# try:
					#     correct_customer_profile = CustomerProfile.objects.get(customer_id=dtb_customer_id, user=request.user)
					#     local_wallet.customer = correct_customer_profile
					# except CustomerProfile.DoesNotExist:
					#     logger.error(f"CustomerProfile with DTB customer ID {dtb_customer_id} not found for user.")
			
			local_wallet.save()  # Ensure this line has the correct number of spaces (likely 12 if inside the 'try' block)
		
		except (DTBServiceError, DTBServiceAPIError) as e:
			logger.error(
				f"DTB Service error when fetching wallet details for user {request.user.id}, wallet ID {local_wallet.wallet_id if local_wallet else 'N/A'}: {e}")
			# Decide if you want to return the stale local data or an error
			# For now, let's return an error indicating data might be stale or service is down
			return Response(
				{"error": "Could not retrieve latest wallet details from provider. Data may be outdated.", "details": str(e)},
				status=status.HTTP_503_SERVICE_UNAVAILABLE
			)
		except Exception as e:
			logger.error(f"Unexpected error when updating wallet for user {request.user.id}: {e}")
			# Generic error
			return Response({"error": "An unexpected error occurred while fetching wallet details."},
			                status=status.HTTP_500_INTERNAL_SERVER_ERROR)
		
		# 4. Serialize the updated (or local, if DTB failed and we chose to return local) wallet data
		serializer = WalletSerializer(local_wallet)
		return Response(serializer.data, status=status.HTTP_200_OK)


class TransactionHistoryPagination(PageNumberPagination):
	page_size = 10
	page_size_query_param = 'page_size'
	max_page_size = 100


class WalletTransactionHistoryAPIView(generics.ListAPIView):
	permission_classes = [IsAuthenticated]
	serializer_class = TopUpTransactionSerializer
	pagination_class = TransactionHistoryPagination
	
	def get_queryset(self):
		wallet = Wallet.objects.get(user=self.request.user, status='ACTIVE')
		return TopUpTransaction.objects.filter(wallet=wallet).order_by('-created_at')


class WalletDetailsAPIView(APIView):
	permission_classes = [IsAuthenticated]
	
	def get(self, request):
		wallet_id = request.query_params.get('wallet_id')
		
		if not wallet_id:
			return Response(
				{"error": "Wallet ID is required as a query parameter"},
				status=status.HTTP_400_BAD_REQUEST
			)
		
		wallet = get_object_or_404(Wallet, wallet_id=wallet_id)
		
		serializer = WalletDetailsSerializer(wallet)
		return Response(serializer.data, status=status.HTTP_200_OK)


class WalletMovementCallbackAPIView(APIView):
	"""
	Webhook endpoint for wallet movement notifications.
	Receives callbacks when money is credited to or debited from a wallet.
	"""
	permission_classes = []  # Allow unauthenticated access for webhook callbacks
	
	# Mapping DTB transaction types to our internal transaction types
	DTB_TO_INTERNAL_TYPE_MAPPING = {
		'tfr.debit.withdrawal.ke_dtb_mpesa': 'WALLET_TO_MPESA',
		'tfr.debit.withdrawal.ke_dtb_eft': 'WALLET_TO_BANK',
		'tfr.debit.fee.withdrawal.ke_dtb_mpesa': 'FEE',
		'tfr.debit.fee.withdrawal.ke_dtb_eft': 'FEE',
		'tfr.credit.topup': 'TOPUP',
		'tfr.debit.transfer': 'WALLET_TO_WALLET',
		'tfr.credit.transfer': 'WALLET_TO_WALLET',
		'tfr.credit.refund': 'REFUND',
		'tfr.debit.reversal': 'REVERSAL',
		'tfr.credit.adjustment': 'ADJUSTMENT',
		'tfr.debit.adjustment': 'ADJUSTMENT',
	}
	
	def post(self, request):
		data = request.data
		transaction_id = data.get('transactionId')
		wallet_id = data.get('walletId')
		transaction_type = data.get('type')
		transaction_date = data.get('date')
		amount = data.get('amount')
		currency = data.get('currency')
		balance = data.get('balance')
		description = data.get('description')
		external_id = data.get('externalId')
		external_unique_id = data.get('externalUniqueId')
		other_wallet_id = data.get('otherWalletId')
		location = data.get('location')
		
		logger.info(f"Wallet movement callback received: {data}")
		
		try:
			# Find the wallet
			wallet = Wallet.objects.get(wallet_id=wallet_id)
			
			# Update wallet balance with the latest balance from callback
			wallet.current_balance = balance
			# For available balance, we'll use the same value unless there are reservations
			wallet.available_balance = balance - float(wallet.reservations or 0)
			wallet.save()
			
			# Determine if this is a fee transaction
			is_fee_transaction = 'fee' in transaction_type.lower()
			
			# Map DTB transaction type to internal type
			internal_transaction_type = self.DTB_TO_INTERNAL_TYPE_MAPPING.get(
				transaction_type.lower(), 
				'ADJUSTMENT'  # Default to adjustment for unknown types
			)
			
			# Check if we have a corresponding transaction record
			transaction = None
			if external_unique_id and not is_fee_transaction:
				# Try to find the transaction by external_unique_id
				try:
					# First try to find in Transaction model (wallet-to-wallet, wallet-to-mpesa)
					try:
						uuid_external_id = uuid.UUID(external_unique_id)
						transaction = Transaction.objects.get(external_unique_id=uuid_external_id)
						transaction_found = True
					except (ValueError, Transaction.DoesNotExist):
						transaction_found = False
					
					# If not found in Transaction, try TopUpTransaction
					if not transaction_found:
						try:
							uuid_external_id = uuid.UUID(external_unique_id)
							transaction = TopUpTransaction.objects.get(external_unique_id=uuid_external_id)
							transaction_found = True
						except (ValueError, TopUpTransaction.DoesNotExist):
							transaction_found = False
					
					# If still not found, try other fields
					if not transaction_found:
						# Try Transaction model with other fields
						transaction = Transaction.objects.filter(
							Q(reference=external_unique_id) | 
							Q(external_reference_id=external_unique_id)
						).first()
						
						if not transaction:
							# Try TopUpTransaction model
							transaction = TopUpTransaction.objects.filter(
								Q(payment_reference=external_unique_id)
							).first()
					
					# If no existing transaction found, create a new one for untracked movements
					if not transaction and internal_transaction_type in ['REFUND', 'REVERSAL', 'ADJUSTMENT']:
						transaction = Transaction.objects.create(
							external_unique_id=uuid.uuid4(),  # Generate new UUID
							external_reference_id=external_unique_id,
							transaction_type=internal_transaction_type,
							amount=abs(amount),
							from_wallet=wallet if amount < 0 else None,
							to_wallet=wallet if amount > 0 else None,
							currency=currency,
							status='SUCCESSFUL',  # Movement already happened
							user=wallet.user,
							customer=wallet.customer,
							description=description or f"System {internal_transaction_type.lower()}",
							gateway_transaction_id=str(transaction_id),
						)
						logger.info(f"Created new transaction for untracked movement: {transaction.transaction_id}")
						
					if transaction:
						# Update transaction with callback data
						if isinstance(transaction, Transaction):
							if not transaction.gateway_transaction_id and transaction_id:
								transaction.gateway_transaction_id = str(transaction_id)
							
							# Store the callback data in extra_info
							if not transaction.extra_info:
								transaction.extra_info = {}
							transaction.extra_info['wallet_movement_callback'] = {
								'transaction_id': transaction_id,
								'type': transaction_type,
								'date': transaction_date,
								'balance_after': float(balance),
								'other_wallet_id': other_wallet_id,
								'location': location,
								'internal_type': internal_transaction_type
							}
							
							# Update status based on movement type and amount
							if transaction.status == 'PENDING':
								if amount < 0:  # Debit means transaction went through
									transaction.status = 'SUCCESSFUL'
								elif amount > 0 and internal_transaction_type in ['REFUND', 'REVERSAL']:
									transaction.status = 'REVERSED' if internal_transaction_type == 'REVERSAL' else 'SUCCESSFUL'
							
							transaction.save()
							logger.info(f"Updated transaction {transaction.transaction_id} with wallet movement data")
							
						elif isinstance(transaction, TopUpTransaction):
							if not transaction.gateway_transaction_id and transaction_id:
								transaction.gateway_transaction_id = str(transaction_id)
							
							# Store the callback data in extra_info
							if not transaction.extra_info:
								transaction.extra_info = {}
							transaction.extra_info['wallet_movement_callback'] = {
								'transaction_id': transaction_id,
								'type': transaction_type,
								'date': transaction_date,
								'balance_after': float(balance),
								'other_wallet_id': other_wallet_id,
								'location': location,
								'internal_type': internal_transaction_type
							}
							
							# Update status if transaction was pending
							if transaction.status == 'PENDING' and amount > 0:  # Credit means top-up went through
								transaction.status = 'SUCCESSFUL'
							
							transaction.save()
							logger.info(f"Updated top-up transaction {transaction.payment_id} with wallet movement data")
							
				except Exception as e:
					logger.error(f"Error finding/updating transaction for external_unique_id {external_unique_id}: {e}")
			
			# Handle fee transactions
			if is_fee_transaction and external_id:
				# Try to find the main transaction and update its fee
				try:
					# Fee transactions typically reference the main transaction's ID
					# First try Transaction model
					main_transaction = Transaction.objects.filter(
						Q(withdrawal_id=external_id) |
						Q(external_reference_id=external_id) |
						Q(reference=external_id)
					).first()
					
					if not main_transaction:
						# Try TopUpTransaction model
						main_transaction = TopUpTransaction.objects.filter(
							Q(payment_id=external_id) |
							Q(payment_reference=external_id)
						).first()
					
					if main_transaction and abs(amount) > 0:
						# Update the fee amount (fees are negative in callbacks)
						main_transaction.fee = abs(amount)
						if not main_transaction.extra_info:
							main_transaction.extra_info = {}
						main_transaction.extra_info['fee_callback'] = {
							'transaction_id': transaction_id,
							'type': transaction_type,
							'date': transaction_date,
							'fee_amount': abs(amount),
							'other_wallet_id': other_wallet_id,
							'internal_type': internal_transaction_type
						}
						main_transaction.save()
						
						if isinstance(main_transaction, Transaction):
							logger.info(f"Updated transaction {main_transaction.transaction_id} with fee information")
						else:
							logger.info(f"Updated top-up transaction {main_transaction.payment_id} with fee information")
				except Exception as e:
					logger.error(f"Error updating fee for transaction {external_id}: {e}")
			
			# Log wallet movement for audit purposes
			logger.info(
				f"Wallet {wallet_id} movement: {transaction_type} ({internal_transaction_type}) "
				f"Amount: {amount} {currency}, Balance: {balance}, "
				f"Description: {description}, External ID: {external_unique_id}"
			)
			
			return Response({"message": "Wallet movement callback processed successfully"}, status=status.HTTP_200_OK)
			
		except Wallet.DoesNotExist:
			logger.error(f"Wallet movement callback received for unknown wallet: {wallet_id}")
			return Response({"error": "Wallet not found"}, status=status.HTTP_404_NOT_FOUND)
		
		except Exception as e:
			logger.error(f"Error processing wallet movement callback: {e}")
			return Response({"error": "An unexpected error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ManualRatificationWebhookAPIView(APIView):
	"""
	Webhook endpoint for manual ratification notifications from DTB.
	Handles callbacks when DTB team performs manual ratification for customers.
	"""
	permission_classes = []  # Allow unauthenticated access for webhook callbacks
	
	def post(self, request):
		# Print webhook hit confirmation (for Docker logs)
		print(f"[MANUAL RATIFICATION WEBHOOK] Webhook hit at {timezone.now()}")
		print(f"[MANUAL RATIFICATION WEBHOOK] Request method: {request.method}")
		print(f"[MANUAL RATIFICATION WEBHOOK] Request headers: {dict(request.headers)}")
		
		# Also use logger for Django logging system
		logger.info(f"[MANUAL RATIFICATION WEBHOOK] Webhook hit at {timezone.now()}")
		logger.info(f"[MANUAL RATIFICATION WEBHOOK] Request method: {request.method}")
		
		data = request.data
		print(f"[MANUAL RATIFICATION WEBHOOK] Complete incoming data: {data}")
		logger.info(f"[MANUAL RATIFICATION WEBHOOK] Complete incoming data: {data}")
		
		event_type = data.get('eventType')
		tenant_id = data.get('tenantId')
		created = data.get('created')
		trace_id = data.get('traceId')
		
		# Extract the main data
		webhook_data = data.get('data', {})
		ratify_result_data = webhook_data.get('ratifyResultData')
		
		# Extract entity information
		associated_entity_id = data.get('associatedEntityId')
		associated_entity_type = data.get('associatedEntityType')
		
		# Extract instigator information
		instigator = data.get('instigator', {})
		instigator_identity = instigator.get('identity')
		
		print(f"[MANUAL RATIFICATION WEBHOOK] Extracted data - Event: {event_type}, Entity ID: {associated_entity_id}, Entity Type: {associated_entity_type}, Instigator: {instigator_identity}")
		
		logger.info(f"Manual ratification webhook received: eventType={event_type}, entityId={associated_entity_id}, entityType={associated_entity_type}")
		
		try:
			# Validate event type
			if event_type != 'user.manual.ratify.create':
				logger.warning(f"Unexpected event type received: {event_type}")
				return Response({"message": "Event type not supported"}, status=status.HTTP_200_OK)
			
			# Only handle customer ratifications (userId)
			if associated_entity_type != 'userId':
				logger.info(f"Skipping ratification for entity type: {associated_entity_type}")
				return Response({"message": "Entity type not supported"}, status=status.HTTP_200_OK)
			
			# Find the customer profile by customer_id
			try:
				customer_profiles = CustomerProfile.objects.filter(customer_id=associated_entity_id)
				
				if customer_profiles.count() == 0:
					print(f"[MANUAL RATIFICATION WEBHOOK] ERROR: Customer not found for ID: {associated_entity_id}")
					logger.error(f"Manual ratification webhook received for unknown customer: {associated_entity_id}")
					return Response({"error": "Customer not found"}, status=status.HTTP_404_NOT_FOUND)
				elif customer_profiles.count() > 1:
					print(f"[MANUAL RATIFICATION WEBHOOK] WARNING: Multiple CustomerProfile records found for customer_id {associated_entity_id}. Count: {customer_profiles.count()}")
					logger.warning(f"Multiple CustomerProfile records found for customer_id {associated_entity_id}. Count: {customer_profiles.count()}. Using the first one.")
					
					# Log details of all duplicate records for investigation
					for i, profile in enumerate(customer_profiles):
						logger.warning(f"Duplicate {i+1}: CustomerProfile ID={profile.id}, User ID={profile.user.id}, User={profile.user.get_full_name()}, KYC Status={profile.kyc_status}")
					
					customer_profile = customer_profiles.first()
				else:
					customer_profile = customer_profiles.first()
				
				print(f"[MANUAL RATIFICATION WEBHOOK] Customer found: {customer_profile.customer_id} - Current KYC Status: {customer_profile.kyc_status}")
				
			except Exception as e:
				print(f"[MANUAL RATIFICATION WEBHOOK] ERROR: Exception while finding customer: {e}")
				logger.error(f"Exception while finding customer profile for ID {associated_entity_id}: {e}")
				return Response({"error": "Error finding customer profile"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
			
			# Parse the ratification result data
			import json
			try:
				ratify_results = json.loads(ratify_result_data) if isinstance(ratify_result_data, str) else ratify_result_data
				logger.info(f"[MANUAL RATIFICATION WEBHOOK] Parsed ratification results: {ratify_results}")
			except (json.JSONDecodeError, TypeError) as e:
				logger.error(f"Failed to parse ratifyResultData: {e}")
				return Response({"error": "Invalid ratification data format"}, status=status.HTTP_400_BAD_REQUEST)
			
			# Check if manual ratification passed
			manual_ratify_check = ratify_results.get('manualRatify', {})
			manual_ratify_passed = manual_ratify_check.get('passed', False)
			logger.info(f"[MANUAL RATIFICATION WEBHOOK] Manual ratification result: {'PASSED' if manual_ratify_passed else 'FAILED'}")
			
			# Store the old status for comparison
			old_status = customer_profile.kyc_status
			
			# Update customer profile based on manual ratification result
			if manual_ratify_passed:
				customer_profile.kyc_status = 'APPROVED'
				customer_profile.kyc_failure_stage = None
				customer_profile.kyc_error_message = None
				
				# Store manual ratification details
				if not customer_profile.kyc_error_message:
					customer_profile.kyc_error_message = ""
				
				# Add manual ratification note
				manual_ratification_note = f"Manual ratification approved by {instigator_identity} on {created}"
				if customer_profile.kyc_error_message:
					customer_profile.kyc_error_message += f"\n{manual_ratification_note}"
				else:
					customer_profile.kyc_error_message = manual_ratification_note
			else:
				customer_profile.kyc_status = 'FAILED'
				customer_profile.kyc_failure_stage = 'Manual Ratification'
				
				# Extract failed checks for error message
				failed_checks = []
				for check_name, check_data in ratify_results.items():
					if isinstance(check_data, dict) and check_data.get('checked', False) and not check_data.get('passed', False):
						failed_checks.append(check_name)
				
				customer_profile.kyc_error_message = f"Manual ratification failed. Failed checks: {', '.join(failed_checks)}"
			
			# Store the complete webhook data for audit purposes
			webhook_audit = {
				'timestamp': timezone.now().isoformat(),
				'event_type': event_type,
				'trace_id': trace_id,
				'tenant_id': tenant_id,
				'instigator': instigator_identity,
				'ratification_result': manual_ratify_passed,
				'full_data': data
			}
			
			# Store webhook audit in extra field (you might want to add this field to CustomerProfile model)
			if not hasattr(customer_profile, 'webhook_audit'):
				# For now, we'll store it in kyc_error_message as a JSON string
				# In production, consider adding a dedicated JSONField for webhook_audit
				pass
			
			customer_profile.save()
			
			# Log the status change
			logger.info(f"[MANUAL RATIFICATION WEBHOOK] Manual ratification processed for customer {customer_profile.customer_id}: {old_status} -> {customer_profile.kyc_status}")
			
			# Send notification emails and handle wallet creation
			if customer_profile.kyc_status == 'APPROVED' and old_status != 'APPROVED':
				logger.info(f"[MANUAL RATIFICATION WEBHOOK] Customer approved - Sending success notification and attempting wallet creation")
				
				# Send success notification
				send_mail(
					subject="Manual KYC Ratification Approved - Customer Ready for Wallet Creation",
					message=f"Customer {customer_profile.customer_id} ({customer_profile.user.get_full_name()}) has been manually approved for KYC by {instigator_identity}. They can now create a wallet.",
					from_email=settings.DEFAULT_FROM_EMAIL,
					recipient_list=settings.DEFAULT_EMAIL_RECEIVERS,
					fail_silently=False,
				)
				
				# Auto-create wallet
				try:
					logger.info(f"[MANUAL RATIFICATION WEBHOOK] Attempting to auto-create wallet for manually ratified customer {customer_profile.customer_id}")
					wallet = create_wallet_for_customer(customer_profile)
					logger.info(f"[MANUAL RATIFICATION WEBHOOK] Wallet created successfully: {wallet.wallet_id}")
				except WalletCreationError as e:
					logger.error(f"[MANUAL RATIFICATION WEBHOOK] Auto-creation of wallet failed after manual ratification for customer {customer_profile.customer_id}: {e}")
					# Optionally send another email to admins about the failure
					send_mail(
						subject="URGENT: Wallet Auto-Creation Failed After Manual Ratification",
						message=f"Failed to auto-create wallet for customer {customer_profile.customer_id} ({customer_profile.user.get_full_name()}) after manual KYC approval. Error: {str(e)}",
						from_email=settings.DEFAULT_FROM_EMAIL,
						recipient_list=settings.DEFAULT_EMAIL_RECEIVERS,
						fail_silently=False,
					)
			elif customer_profile.kyc_status == 'FAILED':
				print(f"[MANUAL RATIFICATION WEBHOOK] Customer failed ratification - Sending failure notification")
				
				# Send failure notification
				send_mail(
					subject="Manual KYC Ratification Failed - Customer Requires Further Review",
					message=f"Customer {customer_profile.customer_id} ({customer_profile.user.get_full_name()}) has failed manual KYC ratification by {instigator_identity}. Error: {customer_profile.kyc_error_message}",
					from_email=settings.DEFAULT_FROM_EMAIL,
					recipient_list=settings.DEFAULT_EMAIL_RECEIVERS,
					fail_silently=False,
				)
			
			print(f"[MANUAL RATIFICATION WEBHOOK] Processing completed successfully - Final status: {customer_profile.kyc_status}")
			
			return Response({
				"message": "Manual ratification webhook processed successfully",
				"customer_id": customer_profile.customer_id,
				"kyc_status": customer_profile.kyc_status,
				"manual_ratify_passed": manual_ratify_passed
			}, status=status.HTTP_200_OK)
		
		except Exception as e:
			print(f"[MANUAL RATIFICATION WEBHOOK] ERROR: Exception occurred during processing - {e}")
			logger.error(f"Error processing manual ratification webhook: {e}")
			return Response({"error": "An unexpected error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
