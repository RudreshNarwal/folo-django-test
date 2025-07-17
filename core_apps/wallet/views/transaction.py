import logging
import uuid
from django.conf import settings
from django.db import transaction as db_transaction
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status, generics
from django.db.models import Q, Sum, Count
from itertools import chain
from operator import attrgetter
from decimal import Decimal

from .core import TransactionHistoryPagination
from ..models import Transaction, Wallet, CustomerProfile, UserContact, TopUpTransaction
from core_apps.users.models import User
from ..serializers import (
    TransactionSerializer, 
    WalletToWalletTransferSerializer,
    WalletToMpesaTransferSerializer,
    WithdrawalFeeRequestSerializer,
    WithdrawalFeeResponseSerializer,
    UserContactSerializer,
    CheckContactWalletRequestSerializer
)
from ..services.dtb_services import (
    DTBService,
    DTBServiceError,
    DTBServiceAuthenticationError,
    DTBServiceAPIError,
)
from ..tasks import schedule_transaction_timeout_check

logger = logging.getLogger(__name__)


# Event Manager Mixin
class TransactionEventManagerMixin:
    """Mixin to handle transaction event emissions."""
    def _emit_transaction_event(self, transaction, old_status, new_status):
        """Helper method to emit a transaction status change event."""
        if old_status == new_status:
            return  # No change, no event

        try:
            # Determine transaction_id based on instance type
            if isinstance(transaction, Transaction):
                transaction_id = str(transaction.transaction_id)
                user_id = transaction.user.id
            elif isinstance(transaction, TopUpTransaction):
                transaction_id = str(transaction.external_unique_id)
                user_id = transaction.wallet.user.id
            else:
                logger.warning("Attempted to emit event for unknown transaction type.")
                return

            event_data = {
                "transaction_id": transaction_id,
                "old_status": old_status,
                "new_status": new_status,
                "timestamp": timezone.now().isoformat(),
                "user_id": user_id
            }
            
            # Log the event. Replace with your actual event system (WebSockets, etc.)
            logger.info(f"Transaction status event: {event_data}")
            
        except Exception as e:
            logger.error(f"Error emitting status event: {e}")


# Helper function to get or create/update contact
def get_or_create_update_contact(user, phone_number, name=None):
    contact, created = UserContact.objects.get_or_create(
        user=user,
        phone_number=phone_number,
        defaults={'name': name, 'last_used': timezone.now()}
    )
    if not created:
        # Update name if provided and different, always update last_used
        if name and contact.name != name:
            contact.name = name
        contact.last_used = timezone.now()
        contact.save(update_fields=['name', 'last_used'] if name else ['last_used'])
    return contact


class WalletToWalletTransferAPIView(APIView):
    """API view for wallet-to-wallet transfers."""
    permission_classes = [IsAuthenticated]
    
    @db_transaction.atomic
    def post(self, request):
        # Pass request context to the serializer for user authentication
        serializer = WalletToWalletTransferSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Get validated data
        to_wallet_id = serializer.validated_data['to_wallet_id']
        amount = serializer.validated_data['amount']
        description = serializer.validated_data.get('description', 'Wallet to wallet transfer')
        
        # Get source wallet from serializer
        from_wallet = serializer.wallet
        from_wallet_id = from_wallet.wallet_id
            
        # Get destination wallet
        try:
            to_wallet = Wallet.objects.get(wallet_id=to_wallet_id)
            if to_wallet.status != 'ACTIVE':
                return Response(
                    {"error": "Destination wallet is not active"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Wallet.DoesNotExist:
            return Response(
                {"error": "Destination wallet not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Generate unique ID for the transaction
        external_unique_id = uuid.uuid4()
        
        # Create Transaction record initially as PENDING
        transaction = Transaction.objects.create(
            external_unique_id=external_unique_id,
            transaction_type='WALLET_TO_WALLET',
            amount=amount,
            from_wallet=from_wallet,
            to_wallet=to_wallet,  # Use the actual wallet object
            currency=from_wallet.currency,
            status='PENDING',
            user=request.user,
            customer=from_wallet.customer,
            description=description
        )
        
        # Schedule timeout check for this transaction (5 minutes)
        # Note: Wallet-to-wallet transfers are usually immediate, but we schedule this for consistency
        schedule_transaction_timeout_check.delay(
            str(transaction.transaction_id),
            'wallet_transaction',
            5  # 5 minutes timeout
        )
        
        # Prepare payload for DTB service
        payload = {
            "amount": float(amount),
            "description": description,
            "externalUniqueId": str(external_unique_id),
            "fromWalletId": from_wallet_id,
            "toWalletId": to_wallet_id
        }
        
        # Call DTB service
        dtb_service = DTBService()
        try:
            response_code = dtb_service.wallet_to_wallet_transfer(payload)
            
            # Update transaction status based on response
            if response_code == 204:  # No Content - Success response
                transaction.status = 'SUCCESSFUL'
                transaction.save()
                
                # Update wallet balance (fetch latest)
                wallet_details = dtb_service.get_wallet_details(from_wallet_id)
                from_wallet.available_balance = wallet_details['availableBalance']
                from_wallet.current_balance = wallet_details['currentBalance']
                from_wallet.save()
                
                # Return success response
                return Response({
                    "message": "Transfer completed successfully",
                    "transaction_id": str(transaction.transaction_id),
                    "from_wallet": from_wallet_id,
                    "to_wallet": to_wallet_id,
                    "amount": float(amount),
                    "status": transaction.status
                }, status=status.HTTP_200_OK)
            else:
                # Handle unexpected response
                transaction.status = 'FAILED'
                transaction.save()
                return Response({
                    "error": f"Transfer failed with response code: {response_code}",
                    "transaction_id": str(transaction.transaction_id)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except (DTBServiceAuthenticationError, DTBServiceAPIError) as e:
            # Handle API errors
            transaction.status = 'FAILED'
            transaction.save()
            logger.error(f"DTB API Error during wallet-to-wallet transfer: {e}")
            return Response({
                "error": str(e),
                "transaction_id": str(transaction.transaction_id)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            # Handle unexpected errors
            transaction.status = 'FAILED'
            transaction.save()
            logger.error(f"Unexpected error during wallet-to-wallet transfer: {e}")
            return Response({
                "error": "An unexpected error occurred",
                "transaction_id": str(transaction.transaction_id)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class WalletToMpesaTransferAPIView(TransactionEventManagerMixin, APIView):
    """
    API view for transfers initiated via phone number.
    Performs Wallet-to-MPESA transfer.
    Also creates/updates UserContact for the recipient.
    """
    permission_classes = [IsAuthenticated]

    @db_transaction.atomic
    def post(self, request):
        serializer = WalletToMpesaTransferSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Get validated data
        amount = serializer.validated_data['amount']
        phone_number = serializer.validated_data['phone_number']
        contact_name = serializer.validated_data.get('contact_name')
        description = serializer.validated_data.get('description', 'Transfer') # Generic description initially

        # Get source wallet from serializer
        from_wallet = serializer.wallet
        from_wallet_id = from_wallet.wallet_id
        user = request.user

        # Get or create/update the contact for the user
        contact = get_or_create_update_contact(user, phone_number, contact_name)

        # Removed the check for recipient wallet - always proceed with MPESA

        # Generate unique ID for the transaction
        external_unique_id = uuid.uuid4()
        dtb_service = DTBService()

        # --- Perform Wallet-to-MPESA Transfer ---
        transaction_type = 'WALLET_TO_MPESA'
        final_description = description or f"MPESA payment to {contact.name or phone_number}"
        reference = f"FOLOMONEY-{uuid.uuid4().hex[:8].upper()}" # Example reference

        # Create Transaction record initially as PENDING
        transaction = Transaction.objects.create(
            external_unique_id=external_unique_id,
            transaction_type=transaction_type,
            amount=amount,
            from_wallet=from_wallet,
            to_wallet=None, # Explicitly set to None for MPESA
            currency=from_wallet.currency,
            status='PENDING',
            user=user,
            customer=from_wallet.customer,
            description=final_description,
            deliver_to_phone=phone_number, # Use the target phone number
            reference=reference,
            contact=contact # Link to contact
        )

        # Prepare payload for DTB service
        callback_url = settings.WALLET_WITHDRAWAL_CALLBACK_URL
        payload = {
            "deliverToPhone": phone_number,
            "reference": reference,
            "amount": float(amount),
            "callbackUrl": callback_url,
            "description": final_description,
            "type": "KE_DTB_MPESA",
            "externalUniqueId": str(external_unique_id)
        }

        try:
            response = dtb_service.wallet_to_mpesa_transfer(from_wallet_id, payload)
            # Save tracing context if present
            if 'tracingContext' in response:
                transaction.tracing_context = response.get('tracingContext')
            # Update to handle both SUCCESSFUL and PENDING as valid states
            if response.get('status') in ['SUCCESSFUL', 'PENDING']:
                # Set transaction status based on response status
                transaction.status = response.get('status')
                transaction.withdrawal_id = response.get('withdrawalId')
                transaction.gateway = response.get('gateway')
                transaction.gateway_transaction_id = response.get('gatewayTransactionId')
                transaction.fee = response.get('fee', 0)
                
                # Ensure extra_info is a dictionary
                if not transaction.extra_info:
                    transaction.extra_info = {}
                transaction.extra_info['initiation_response'] = response.get('extraInfo')
                
                transaction.save()

                # Schedule timeout check for this transaction (5 minutes)
                schedule_transaction_timeout_check.delay(
                    str(transaction.transaction_id),
                    'wallet_transaction',
                    5  # 5 minutes timeout
                )

                # Update wallet balance
                wallet_details = dtb_service.get_wallet_details(from_wallet_id)
                from_wallet.available_balance = wallet_details['availableBalance']
                from_wallet.current_balance = wallet_details['currentBalance']
                from_wallet.save()

                status_message = "MPESA withdrawal initiated successfully" 
                if response.get('status') == 'PENDING':
                    status_message = "MPESA withdrawal is being processed"

                # Emit transaction status change event (for real-time updates)
                self._emit_transaction_event(transaction, 'PENDING', response.get('status'))
                
                return Response({
                    "message": status_message,
                    "transaction_id": str(transaction.transaction_id),
                    "withdrawal_id": transaction.withdrawal_id,
                    "amount": float(amount),
                    "fee": float(transaction.fee),
                    "status": transaction.status,
                    "contact_name": contact.name,
                    "contact_phone": contact.phone_number,
                }, status=status.HTTP_200_OK)
            else:
                # Handle failed transaction initiation
                transaction.status = 'FAILED'
                
                # Ensure extra_info is a dictionary before updating
                if not transaction.extra_info:
                    transaction.extra_info = {}
                if 'extraInfo' in response:
                    transaction.extra_info['initiation_response'] = response.get('extraInfo')
                
                transaction.save()
                logger.error(f"DTB MPESA Transfer initiation failed for transaction {transaction.transaction_id}: {response}")
                return Response({
                    "error": "MPESA withdrawal initiation failed",
                    "transaction_id": str(transaction.transaction_id),
                    "status": response.get('status'),
                    "details": response.get('extraInfo', response) # Show extraInfo if available
                }, status=status.HTTP_400_BAD_REQUEST)

        except (DTBServiceAuthenticationError, DTBServiceAPIError) as e:
            transaction.status = 'FAILED'
            transaction.save()
            error_message = str(e)
            # Check if the error message indicates a duplicate external ID from DTB
            # The specific error message structure from DTB might vary.
            if "Duplicate entry" in error_message and "withdrawal.unique_id" in error_message:
                logger.warning(
                    f"DTB reported a duplicate externalUniqueId for local transaction {transaction.transaction_id} "
                    f"(external_unique_id sent: {external_unique_id}). This likely means the request was already processed "
                    f"or registered by DTB. DTB Error: {error_message}"
                )
            else:
                logger.error(
                    f"DTB API Error during wallet-to-MPESA transfer for local transaction {transaction.transaction_id} "
                    f"(external_unique_id sent: {external_unique_id}). Error: {e}"
                )
            
            return Response({
                "error": error_message, # You might choose to return a more generic message for duplicates if desired
                "transaction_id": str(transaction.transaction_id)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            # Handle unexpected errors
            transaction.status = 'FAILED'
            transaction.save()
            logger.error(
                f"Unexpected error during wallet-to-MPESA transfer for local transaction {transaction.transaction_id} "
                f"(external_unique_id sent: {external_unique_id}): {e}"
            )
            return Response({
                "error": "An unexpected error occurred",
                "transaction_id": str(transaction.transaction_id)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MpesaWithdrawalWebhookAPIView(TransactionEventManagerMixin, APIView):
    """
    Webhook endpoint for MPESA withdrawal status updates.
    This should be configured as the callback URL in the MPESA withdrawal request.
    """
    permission_classes = []  # Allow unauthenticated access for webhook callbacks
    def post(self, request):
        data = request.data
        # Handle both old format (withdrawalId) and new format (paymentId)
        payment_id = data.get('paymentId')
        withdrawal_id = data.get('withdrawalId', payment_id)  # Use paymentId as fallback
        external_unique_id = data.get('externalUniqueId')
        status_value = data.get('status')
        
        logger.info(f"MPESA withdrawal webhook received: {data}")
        
        try:
            # Find the transaction by external_unique_id
            transaction = Transaction.objects.get(
                external_unique_id=uuid.UUID(external_unique_id),
                transaction_type='WALLET_TO_MPESA'
            )
            
            # Store old status for event emission
            old_status = transaction.status
            
            # Store the complete webhook response data
            transaction.webhook_response = data
            
            # Update transaction status
            transaction.status = 'SUCCESSFUL' if status_value == 'SUCCESSFUL' else 'FAILED'
            new_status = transaction.status
            
            # Handle payment_id if present (new format)
            if payment_id:
                transaction.external_reference_id = str(payment_id)
            
            # Still save withdrawal_id if present (for backward compatibility)
            if withdrawal_id:
                transaction.withdrawal_id = withdrawal_id
            
            # Update other fields based on new response format
            if data.get('merchantName'):
                # Store merchant info in extra_info if not already present
                if not transaction.extra_info:
                    transaction.extra_info = {}
                transaction.extra_info['merchantName'] = data.get('merchantName')
                transaction.extra_info['merchantId'] = data.get('merchantId', '')
            
            # Handle payment instrument info (contains phone number)
            payment_instrument_info = data.get('paymentInstrumentInfo', {})
            if payment_instrument_info.get('externalWalletId'):
                # This is the phone number in the format 2547XXXXXXX
                phone_number = payment_instrument_info.get('externalWalletId')
                if not transaction.deliver_to_phone:
                    transaction.deliver_to_phone = phone_number
            
            # Update fee
            if data.get('fee') is not None:
                transaction.fee = data.get('fee')
            
            # Ensure extra_info is a dictionary before updating
            if not transaction.extra_info:
                transaction.extra_info = {}
            
            # Store additional fields in extra_info
            transaction.extra_info['paymentType'] = data.get('paymentType')
            transaction.extra_info['created'] = data.get('created')
            transaction.extra_info['errorDescription'] = data.get('errorDescription', '')
            
            # Store payment reference if available
            if data.get('paymentReference'):
                transaction.reference = data.get('paymentReference')
            
            transaction.save()
            
            # If transaction is successful, update wallet balance
            if status_value == 'SUCCESSFUL':
                dtb_service = DTBService()
                wallet_details = dtb_service.get_wallet_details(transaction.from_wallet.wallet_id)
                wallet = transaction.from_wallet
                wallet.available_balance = wallet_details['availableBalance']
                wallet.current_balance = wallet_details['currentBalance']
                wallet.save()
                
            # Emit transaction status change event (for real-time updates)
            self._emit_transaction_event(transaction, old_status, new_status)
                
            return Response({"message": "Webhook processed successfully"}, status=status.HTTP_200_OK)
        
        except Transaction.DoesNotExist:
            logger.error(f"Webhook received for unknown transaction: {external_unique_id}")
            return Response({"error": "Transaction not found"}, status=status.HTTP_404_NOT_FOUND)
        
        except Exception as e:
            logger.error(f"Error processing MPESA withdrawal webhook: {e}")
            return Response({"error": "An unexpected error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TransactionHistoryAPIView(generics.ListAPIView):
    """API view for listing user's complete transaction history."""
    permission_classes = [IsAuthenticated]
    serializer_class = TransactionSerializer
    pagination_class = TransactionHistoryPagination
    
    def get_queryset(self):
        user = self.request.user
        
        # Get user's active wallet
        try:
            wallet = Wallet.objects.get(user=user, status='ACTIVE')
        except Wallet.DoesNotExist:
            return Transaction.objects.none()
        
        # Get all transactions where user's wallet is involved (both incoming and outgoing)
        # This includes:
        # 1. Transactions initiated by the user (user=user)
        # 2. Incoming wallet-to-wallet transfers (to_wallet=user's wallet)
        # 3. System transactions affecting user's wallet (refunds, reversals, adjustments)
        from django.db.models import Q
        
        queryset = Transaction.objects.filter(
            Q(user=user) |  # Transactions initiated by user
            Q(from_wallet=wallet) |  # Outgoing from user's wallet
            Q(to_wallet=wallet)  # Incoming to user's wallet
        ).distinct().order_by('-created_at')
        
        return queryset


class GetWithdrawalFeeAPIView(APIView):
    """API for getting the fee for a wallet withdrawal."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        serializer = WithdrawalFeeRequestSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Get the user's active wallet (same security pattern as other endpoints)
        try:
            wallet = Wallet.objects.get(user=request.user, status='ACTIVE')
        except Wallet.DoesNotExist:
            return Response(
                {"error": "No active wallet found for your account"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Wallet.MultipleObjectsReturned:
            wallet = Wallet.objects.filter(user=request.user, status='ACTIVE').first()
        
        # Get fee from DTB service
        amount = serializer.validated_data['amount']
        withdrawal_type = serializer.validated_data.get('withdrawal_type', 'KE_DTB_MPESA')
        
        try:
            dtb_service = DTBService()
            fee_response = dtb_service.get_withdrawal_fee(wallet.wallet_id, amount, withdrawal_type)
            
            # Use our response serializer to return a cleaner format
            response_serializer = WithdrawalFeeResponseSerializer(fee_response)
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        except (DTBServiceAuthenticationError, DTBServiceAPIError) as e:
            logger.error(f"DTB API Error getting withdrawal fee: {e}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Unexpected error getting withdrawal fee: {e}")
            return Response({"error": "An unexpected error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RecentContactsAPIView(generics.ListAPIView):
    """API view for listing the user's 10 most recently used contacts."""
    permission_classes = [IsAuthenticated]
    serializer_class = UserContactSerializer

    def get_queryset(self):
        user = self.request.user
        # Order by last_used descending and take the top 10
        return UserContact.objects.filter(user=user).order_by('-last_used')[:10]


class CheckContactWalletAPIView(APIView):
    """
    Checks if a contact (by phone number) has an active FoloMoney wallet.
    Creates/updates the contact entry for the requesting user based on input.
    Accepts POST request with phone_number and optional name.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CheckContactWalletRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        phone_number = serializer.validated_data['phone_number']
        contact_name = serializer.validated_data.get('name')
        requesting_user = request.user

        # --- Check for Recipient's Wallet ---
        has_wallet = False
        wallet_id_response = "" # Default to empty string as requested
        try:
            # Assuming User model has a unique 'mobile' field matching the phone_number format
            recipient_user = User.objects.get(mobile=phone_number)
            # Use filter().first() to avoid errors if duplicates somehow exist
            wallet = Wallet.objects.filter(user=recipient_user, status='ACTIVE').first()
            if wallet:
                has_wallet = True
                wallet_id_response = str(wallet.wallet_id) # Use the actual ID as string
        except User.DoesNotExist:
            logger.info(f"User with phone {phone_number} not found during wallet check.")
            pass # No user means no wallet
        except Exception as e:
            # Log error but don't expose details; treat as wallet not found
            logger.error(f"Error checking wallet for phone {phone_number}: {e}")
            has_wallet = False
            wallet_id_response = ""

        # --- Get or Create/Update Contact for the Requesting User ---
        # This happens regardless of whether the recipient has a wallet
        contact = get_or_create_update_contact(requesting_user, phone_number, contact_name)

        # --- Prepare and Return Response ---
        contact_serializer = UserContactSerializer(contact)
        return Response({
            "contact": contact_serializer.data,
            "has_wallet": has_wallet,
            "wallet_id": wallet_id_response
        }, status=status.HTTP_200_OK)


class ContactTransactionHistoryAPIView(generics.ListAPIView):
    """API view for listing transaction history with a specific contact."""
    permission_classes = [IsAuthenticated]
    serializer_class = TransactionSerializer

    def get_queryset(self):
        user = self.request.user
        contact_id = self.kwargs.get('contact_id') # Get contact_id from URL path

        # Fetch the specific contact for the user
        try:
            contact = UserContact.objects.get(user=user, id=contact_id)
        except UserContact.DoesNotExist:
            # Return empty queryset if contact doesn't exist or doesn't belong to user
            return Transaction.objects.none()

        # Filter transactions linked to this user and this contact
        return Transaction.objects.filter(user=user, contact=contact).order_by('-created_at')


class ComprehensiveWalletHistoryAPIView(generics.ListAPIView):
    """
    API view for listing complete wallet history including both 
    Transfer transactions and TopUp transactions in chronological order.
    """
    permission_classes = [IsAuthenticated]
    pagination_class = TransactionHistoryPagination
    
    def get_queryset(self):
        user = self.request.user
        
        # Get the user's active wallet
        try:
            wallet = Wallet.objects.get(user=user, status='ACTIVE')
        except Wallet.DoesNotExist:
            # Return an empty queryset if no active wallet is found
            return Transaction.objects.none()
        
        # Get all Transfer transactions where the user's wallet was the sender or receiver,
        # then order them by the creation date in descending order.
        queryset = Transaction.objects.filter(
            Q(from_wallet=wallet) | Q(to_wallet=wallet)
        ).distinct().order_by('-created_at')
        
        return queryset

    
    # def get_queryset(self):
    #     user = self.request.user
        
    #     # Get user's active wallet
    #     try:
    #         wallet = Wallet.objects.get(user=user, status='ACTIVE')
    #     except Wallet.DoesNotExist:
    #         return []
        
    #     # Get all Transfer transactions where user's wallet is involved
    #     transfer_transactions = Transaction.objects.filter(
    #         Q(user=user) |  # Transactions initiated by user
    #         Q(from_wallet=wallet) |  # Outgoing from user's wallet
    #         Q(to_wallet=wallet)  # Incoming to user's wallet
    #     ).distinct()
        
    #     # Get all TopUp transactions for user's wallet
    #     topup_transactions = TopUpTransaction.objects.filter(wallet=wallet)
        
    #     # Combine and sort by created_at
    #     combined_transactions = sorted(
    #         chain(transfer_transactions, topup_transactions),
    #         key=attrgetter('created_at'),
    #         reverse=True
    #     )
        
    #     return combined_transactions
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        
        # Apply pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serialized_data = []
            for transaction in page:
                if isinstance(transaction, Transaction):
                    serializer = TransactionSerializer(transaction)
                    data = serializer.data
                    data['transaction_category'] = 'TRANSFER'
                elif isinstance(transaction, TopUpTransaction):
                    # Create a unified format for TopUp transactions
                    data = {
                        'transaction_id': str(transaction.payment_id),
                        'transaction_type': 'TOPUP',
                        'amount': transaction.amount,
                        'fee': transaction.fee,
                        'currency': transaction.currency,
                        'status': transaction.status,
                        'description': transaction.description,
                        'created_at': transaction.created_at,
                        'from_wallet_id': None,
                        'to_wallet_id': str(transaction.wallet.wallet_id),
                        'deliver_to_phone': None,
                        'gateway_transaction_id': transaction.gateway_transaction_id,
                        'contact_name': None,
                        'contact_phone': None,
                        'transaction_category': 'TOPUP'
                    }
                serialized_data.append(data)
            
            return self.get_paginated_response(serialized_data)
        
        # If no pagination, return all data
        serialized_data = []
        for transaction in queryset:
            if isinstance(transaction, Transaction):
                serializer = TransactionSerializer(transaction)
                data = serializer.data
                data['transaction_category'] = 'TRANSFER'
            elif isinstance(transaction, TopUpTransaction):
                data = {
                    'transaction_id': str(transaction.payment_id),
                    'transaction_type': 'TOPUP',
                    'amount': transaction.amount,
                    'fee': transaction.fee,
                    'currency': transaction.currency,
                    'status': transaction.status,
                    'description': transaction.description,
                    'created_at': transaction.created_at,
                    'from_wallet_id': None,
                    'to_wallet_id': str(transaction.wallet.wallet_id),
                    'deliver_to_phone': None,
                    'gateway_transaction_id': transaction.gateway_transaction_id,
                    'contact_name': None,
                    'contact_phone': None,
                    'transaction_category': 'TOPUP'
                }
            serialized_data.append(data)
        
        return Response(serialized_data)


class WalletTransactionSummaryAPIView(APIView):
    """
    API view for getting wallet transaction summary and statistics.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        # Get user's active wallet
        try:
            wallet = Wallet.objects.get(user=user, status='ACTIVE')
        except Wallet.DoesNotExist:
            return Response({"error": "No active wallet found"}, status=status.HTTP_404_NOT_FOUND)
        
        # Get date range from query params (optional)
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
        
        # Base querysets
        transfer_qs = Transaction.objects.filter(
            Q(user=user) | Q(from_wallet=wallet) | Q(to_wallet=wallet)
        ).distinct()
        
        topup_qs = TopUpTransaction.objects.filter(wallet=wallet)
        
        # Apply date filters if provided
        if from_date:
            transfer_qs = transfer_qs.filter(created_at__gte=from_date)
            topup_qs = topup_qs.filter(created_at__gte=from_date)
        
        if to_date:
            transfer_qs = transfer_qs.filter(created_at__lte=to_date)
            topup_qs = topup_qs.filter(created_at__lte=to_date)
        
        # Calculate transfer statistics
        outgoing_transfers = transfer_qs.filter(from_wallet=wallet)
        incoming_transfers = transfer_qs.filter(to_wallet=wallet)
        
        outgoing_stats = outgoing_transfers.aggregate(
            total_amount=Sum('amount'),
            total_fees=Sum('fee'),
            count=Count('id')
        )
        
        incoming_stats = incoming_transfers.aggregate(
            total_amount=Sum('amount'),
            count=Count('id')
        )
        
        # Calculate topup statistics
        topup_stats = topup_qs.filter(status='SUCCESSFUL').aggregate(
            total_amount=Sum('amount'),
            total_fees=Sum('fee'),
            count=Count('id')
        )
        
        # Transaction type breakdown
        transaction_types = transfer_qs.values('transaction_type').annotate(
            count=Count('id'),
            total_amount=Sum('amount')
        )
        
        # Status breakdown
        status_breakdown = transfer_qs.values('status').annotate(
            count=Count('id')
        )
        
        # Recent activity (last 7 days)
        from datetime import datetime, timedelta
        seven_days_ago = datetime.now() - timedelta(days=7)
        
        recent_transfers = transfer_qs.filter(created_at__gte=seven_days_ago).count()
        recent_topups = topup_qs.filter(created_at__gte=seven_days_ago).count()
        
        summary = {
            "wallet_info": {
                "wallet_id": str(wallet.wallet_id),
                "current_balance": float(wallet.current_balance),
                "available_balance": float(wallet.available_balance),
                "currency": wallet.currency
            },
            "outgoing_transfers": {
                "total_amount": float(outgoing_stats['total_amount'] or 0),
                "total_fees": float(outgoing_stats['total_fees'] or 0),
                "count": outgoing_stats['count']
            },
            "incoming_transfers": {
                "total_amount": float(incoming_stats['total_amount'] or 0),
                "count": incoming_stats['count']
            },
            "topups": {
                "total_amount": float(topup_stats['total_amount'] or 0),
                "total_fees": float(topup_stats['total_fees'] or 0),
                "count": topup_stats['count']
            },
            "transaction_types": [
                {
                    "type": item['transaction_type'],
                    "count": item['count'],
                    "total_amount": float(item['total_amount'] or 0)
                }
                for item in transaction_types
            ],
            "status_breakdown": [
                {
                    "status": item['status'],
                    "count": item['count']
                }
                for item in status_breakdown
            ],
            "recent_activity": {
                "transfers_last_7_days": recent_transfers,
                "topups_last_7_days": recent_topups
            },
            "date_range": {
                "from_date": from_date,
                "to_date": to_date
            }
        }
        
        return Response(summary, status=status.HTTP_200_OK)


class TransactionStatusAPIView(TransactionEventManagerMixin, APIView):
    """
    API view to get current status of any transaction (Transfer or TopUp).
    
    Query Parameters:
    - refresh: boolean (default: false) - Refresh status from gateway
    - emit_events: boolean (default: false) - Emit real-time events on status change
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, transaction_id):
        try:
            user = request.user
            
            # Get query parameters
            refresh_from_gateway = request.query_params.get('refresh', 'false').lower() == 'true'
            emit_events = request.query_params.get('emit_events', 'false').lower() == 'true'
            
            # Find the transaction
            transaction_data = self._find_transaction(transaction_id, user)
            
            if not transaction_data:
                return Response({
                    "status": "error",
                    "message": "Transaction not found",
                    "code": "TRANSACTION_NOT_FOUND"
                }, status=status.HTTP_404_NOT_FOUND)
            
            transaction_obj, transaction_type = transaction_data
            
            # Refresh from gateway if requested
            old_status = transaction_obj.status
            if refresh_from_gateway and old_status == 'PENDING':
                self._refresh_from_gateway(transaction_obj, transaction_type)
                # Reload to get updated status
                transaction_obj.refresh_from_db()
            
            # Emit events if status changed and events are enabled
            if emit_events and old_status != transaction_obj.status:
                self._emit_transaction_event(transaction_obj, old_status, transaction_obj.status)
            
            # Return formatted response
            return Response({
                "status": "success",
                "data": self._format_transaction_response(transaction_obj, transaction_type)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error retrieving transaction status for {transaction_id}: {str(e)}")
            return Response({
                "status": "error",
                "message": "An error occurred while retrieving transaction status",
                "code": "INTERNAL_ERROR"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _find_transaction(self, transaction_id, user):
        """Find transaction by ID, supporting both UUID and integer formats."""
        # Try regular Transaction first (UUID)
        try:
            transaction_uuid = uuid.UUID(transaction_id)
            transaction = Transaction.objects.filter(
                transaction_id=transaction_uuid,
                user=user
            ).first()
            
            if transaction:
                return (transaction, 'wallet_transaction')
        except (ValueError, TypeError):
            pass
        
        # Try TopUpTransaction by external_unique_id (UUID)
        try:
            topup_uuid = uuid.UUID(transaction_id)
            topup = TopUpTransaction.objects.filter(
                external_unique_id=topup_uuid,
                wallet__user=user
            ).first()
            
            if topup:
                return (topup, 'topup_transaction')
        except (ValueError, TypeError):
            pass
        
        # Try TopUpTransaction by payment_id (integer)
        try:
            payment_id = int(transaction_id)
            topup = TopUpTransaction.objects.filter(
                payment_id=payment_id,
                wallet__user=user
            ).first()
            
            if topup:
                return (topup, 'topup_transaction')
        except (ValueError, TypeError):
            pass
        
        return None
    
    def _refresh_from_gateway(self, transaction_obj, transaction_type):
        """Refresh transaction status from DTB gateway."""
        try:
            dtb_service = DTBService()
            
            if transaction_type == 'wallet_transaction':
                if transaction_obj.transaction_type == 'WALLET_TO_MPESA' and transaction_obj.withdrawal_id:
                    # Check MPESA withdrawal status
                    response = dtb_service.get_withdrawal_status(
                        transaction_obj.from_wallet.wallet_id,
                        transaction_obj.withdrawal_id
                    )
                    
                    new_status = response.get('status', transaction_obj.status) if isinstance(response, dict) else transaction_obj.status
                    if new_status != transaction_obj.status:
                        transaction_obj.status = new_status
                        
                        if isinstance(response, dict) and response.get('errorDescription'):
                            if not transaction_obj.extra_info:
                                transaction_obj.extra_info = {}
                            transaction_obj.extra_info['error_description_from_refresh'] = response.get('errorDescription')
                        
                        transaction_obj.save()
                
                elif transaction_obj.transaction_type in ['WALLET_TO_BANK', 'WALLET_TO_PESALINK']:
                    # For bank transfers, update wallet balance
                    wallet_details = dtb_service.get_wallet_details(transaction_obj.from_wallet.wallet_id)
                    wallet = transaction_obj.from_wallet
                    wallet.available_balance = wallet_details['availableBalance']
                    wallet.current_balance = wallet_details['currentBalance']
                    wallet.save()
            
            elif transaction_type == 'topup_transaction':
                # Check topup status
                response = dtb_service.get_top_up_status(
                    transaction_obj.wallet.wallet_id,
                    transaction_obj.payment_id
                )
                
                new_status = response.get('status', transaction_obj.status) if isinstance(response, dict) else transaction_obj.status
                if new_status != transaction_obj.status:
                    transaction_obj.status = new_status
                    
                    if new_status == 'ERROR_PERM':
                        transaction_obj.error_description = response.get('description', '') if isinstance(response, dict) else ''
                    
                    transaction_obj.gateway = response.get('gateway', '') if isinstance(response, dict) else ''
                    transaction_obj.gateway_transaction_id = response.get('gatewayTransactionId', '') if isinstance(response, dict) else ''
                    transaction_obj.save()
                    
                    logger.info(f"Updated topup {transaction_obj.payment_id} status: {new_status}")
                    
                    # Update wallet balance if successful
                    if new_status == 'SUCCESSFUL':
                        wallet_details = dtb_service.get_wallet_details(transaction_obj.wallet.wallet_id)
                        wallet = transaction_obj.wallet
                        wallet.available_balance = wallet_details['availableBalance']
                        wallet.current_balance = wallet_details['currentBalance']
                        wallet.save()
                        
        except DTBServiceAPIError as e:
            logger.error(f"Error refreshing status from gateway (API Error {e.status_code}): {e.message}")
        except Exception as e:
            logger.error(f"Error refreshing status from gateway: {e}")
    
    def _format_transaction_response(self, transaction_obj, transaction_type):
        """Format transaction data for API response."""
        if transaction_type == 'wallet_transaction':
            return {
                "transaction_id": str(transaction_obj.transaction_id),
                "external_unique_id": str(transaction_obj.external_unique_id),
                "type": transaction_obj.transaction_type,
                "amount": str(transaction_obj.amount),
                "fee": str(transaction_obj.fee),
                "currency": transaction_obj.currency,
                "status": transaction_obj.status,
                "description": transaction_obj.description or "",
                "created_at": transaction_obj.created_at.isoformat(),
                "updated_at": transaction_obj.updated_at.isoformat(),
                "from_wallet_id": str(transaction_obj.from_wallet.wallet_id) if transaction_obj.from_wallet else None,
                "to_wallet_id": str(transaction_obj.to_wallet.wallet_id) if transaction_obj.to_wallet else None,
                "deliver_to_phone": transaction_obj.deliver_to_phone,
                "reference": transaction_obj.reference,
                "withdrawal_id": transaction_obj.withdrawal_id,
                "gateway_transaction_id": transaction_obj.gateway_transaction_id,
                "gateway": transaction_obj.gateway,
                "contact_info": {
                    "name": transaction_obj.contact.name if transaction_obj.contact else None,
                    "phone": transaction_obj.contact.phone_number if transaction_obj.contact else None
                } if transaction_obj.contact else None,
                "bank_beneficiary_info": {
                    "account_holder_name": transaction_obj.bank_beneficiary.account_holder_name,
                    "account_number": transaction_obj.bank_beneficiary.account_number,
                    "bank_name": transaction_obj.bank_beneficiary.bank_name,
                    "nickname": transaction_obj.bank_beneficiary.nickname
                } if transaction_obj.bank_beneficiary else None,
                "error_info": transaction_obj.extra_info.get('error_description_from_refresh') if isinstance(transaction_obj.extra_info, dict) else None
            }
        
        else:  # topup_transaction
            return {
                "transaction_id": str(transaction_obj.external_unique_id),
                "payment_id": transaction_obj.payment_id,
                "type": "TOPUP",
                "amount": str(transaction_obj.amount),
                "fee": str(transaction_obj.fee),
                "currency": transaction_obj.currency,
                "status": transaction_obj.status,
                "description": transaction_obj.description or "",
                "created_at": transaction_obj.created_at.isoformat(),
                "wallet_id": str(transaction_obj.wallet.wallet_id),
                "payment_type": transaction_obj.payment_type,
                "merchant_name": transaction_obj.merchant_name,
                "gateway_transaction_id": transaction_obj.gateway_transaction_id,
                "gateway": transaction_obj.gateway,
                "payment_reference": transaction_obj.payment_reference,
                "error_description": transaction_obj.error_description
            }
    
    def _emit_status_event(self, transaction_obj, old_status, new_status):
        """Emit transaction status change event (optional)."""
        try:
            event_data = {
                "transaction_id": str(getattr(transaction_obj, 'transaction_id', transaction_obj.external_unique_id)),
                "old_status": old_status,
                "new_status": new_status,
                "timestamp": timezone.now().isoformat(),
                "user_id": getattr(transaction_obj, 'user_id', transaction_obj.wallet.user.id)
            }
            
            # Log the event (you can extend this to use WebSockets, Redis, etc.)
            logger.info(f"Transaction status event: {event_data}")
            
            # TODO: Implement your preferred event system here
            # Examples:
            # - WebSocket broadcast
            # - Redis pub/sub
            # - Push notification
            # - Database event log
            
        except Exception as e:
            logger.error(f"Error emitting status event: {e}")

    def _emit_transaction_event(self, transaction, old_status, new_status):
        """Helper method to emit a transaction status change event."""
        # Implementation of emitting a transaction status change event
        # This is a placeholder and should be replaced with the actual implementation
        # based on your event system or notification service
        logger.info(f"Transaction {transaction.transaction_id} status changed from {old_status} to {new_status}")
