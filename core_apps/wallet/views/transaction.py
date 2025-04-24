import logging
import uuid
from django.conf import settings
from django.db import transaction as db_transaction
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status, generics

from ..models import Transaction, Wallet, CustomerProfile, UserContact
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

logger = logging.getLogger(__name__)


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


class WalletToMpesaTransferAPIView(APIView):
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

            if response.get('status') == 'SUCCESSFUL':
                transaction.status = 'SUCCESSFUL'
                transaction.withdrawal_id = response.get('withdrawalId')
                transaction.gateway = response.get('gateway')
                transaction.gateway_transaction_id = response.get('gatewayTransactionId')
                transaction.fee = response.get('fee', 0)
                transaction.extra_info = response.get('extraInfo')
                transaction.save()

                # Update wallet balance
                wallet_details = dtb_service.get_wallet_details(from_wallet_id)
                from_wallet.available_balance = wallet_details['availableBalance']
                from_wallet.current_balance = wallet_details['currentBalance']
                from_wallet.save()

                return Response({
                    "message": "MPESA withdrawal initiated successfully",
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
                if 'extraInfo' in response:
                    transaction.extra_info = response.get('extraInfo')
                transaction.save()
                logger.error(f"DTB MPESA Transfer initiation failed: {response}")
                return Response({
                    "error": "MPESA withdrawal initiation failed",
                    "transaction_id": str(transaction.transaction_id),
                    "status": response.get('status'),
                    "details": response.get('extraInfo', response) # Show extraInfo if available
                }, status=status.HTTP_400_BAD_REQUEST)

        except (DTBServiceAuthenticationError, DTBServiceAPIError, Exception) as e:
            transaction.status = 'FAILED'
            transaction.save()
            logger.error(f"Error during wallet-to-MPESA transfer: {e}")
            error_message = str(e) if isinstance(e, (DTBServiceAuthenticationError, DTBServiceAPIError)) else "An unexpected error occurred"
            return Response({
                "error": error_message,
                "transaction_id": str(transaction.transaction_id)
            }, status=status.HTTP_400_BAD_REQUEST if isinstance(e, (DTBServiceAuthenticationError, DTBServiceAPIError)) else status.HTTP_500_INTERNAL_SERVER_ERROR)


class MpesaWithdrawalWebhookAPIView(APIView):
    """
    Webhook endpoint for MPESA withdrawal status updates.
    This should be configured as the callback URL in the MPESA withdrawal request.
    """
    def post(self, request):
        data = request.data
        withdrawal_id = data.get('withdrawalId')
        external_unique_id = data.get('externalUniqueId')
        status_value = data.get('status')
        
        logger.info(f"MPESA withdrawal webhook received: {data}")
        
        try:
            # Find the transaction by external_unique_id
            transaction = Transaction.objects.get(
                external_unique_id=uuid.UUID(external_unique_id),
                transaction_type='WALLET_TO_MPESA'
            )
            
            # Store the complete webhook response data
            transaction.webhook_response = data
            
            # Update transaction status
            transaction.status = 'SUCCESSFUL' if status_value == 'SUCCESSFUL' else 'FAILED'
            transaction.withdrawal_id = withdrawal_id
            
            # Update other fields if available
            if data.get('gateway'):
                transaction.gateway = data.get('gateway')
            if data.get('gatewayTransactionId'):
                transaction.gateway_transaction_id = data.get('gatewayTransactionId')
            if data.get('fee'):
                transaction.fee = data.get('fee')
            if data.get('extraInfo'):
                transaction.extra_info = data.get('extraInfo')
                
            transaction.save()
            
            # If transaction is successful, update wallet balance
            if status_value == 'SUCCESSFUL':
                dtb_service = DTBService()
                wallet_details = dtb_service.get_wallet_details(transaction.from_wallet.wallet_id)
                wallet = transaction.from_wallet
                wallet.available_balance = wallet_details['availableBalance']
                wallet.current_balance = wallet_details['currentBalance']
                wallet.save()
                
            return Response({"message": "Webhook processed successfully"}, status=status.HTTP_200_OK)
        
        except Transaction.DoesNotExist:
            logger.error(f"Webhook received for unknown transaction: {external_unique_id}")
            return Response({"error": "Transaction not found"}, status=status.HTTP_404_NOT_FOUND)
        
        except Exception as e:
            logger.error(f"Error processing MPESA withdrawal webhook: {e}")
            return Response({"error": "An unexpected error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TransactionHistoryAPIView(generics.ListAPIView):
    """API view for listing user's transaction history."""
    permission_classes = [IsAuthenticated]
    serializer_class = TransactionSerializer
    
    def get_queryset(self):
        user = self.request.user
        return Transaction.objects.filter(user=user).order_by('-created_at')


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
