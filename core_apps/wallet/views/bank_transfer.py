import logging
import uuid
from django.conf import settings
from django.db import transaction as db_transaction
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from ..models import Transaction, Wallet, BankBeneficiary
from ..serializers import (
    WalletToBankTransferSerializer,
    BankTransferFeeRequestSerializer,
    BankTransferFeeResponseSerializer
)
from ..services.dtb_services import (
    DTBService,
    DTBServiceError,
    DTBServiceAuthenticationError,
    DTBServiceAPIError,
    DTBServiceSCAChallengeError,
)
from ..utils.payload_ordering import create_pesalink_payload, create_eft_payload, create_ift_payload
from ..tasks import schedule_transaction_timeout_check

logger = logging.getLogger(__name__)




class WalletToBankTransferAPIView(APIView):
    """
    API view for transfers from wallet to bank accounts.
    Supports both PesaLink and EFT transfers.
    """
    permission_classes = [IsAuthenticated]

    @db_transaction.atomic
    def post(self, request):
        serializer = WalletToBankTransferSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Get validated data
        amount = serializer.validated_data['amount']
        transfer_type = serializer.validated_data['transfer_type']
        description = serializer.validated_data.get('description', f'{transfer_type} transfer')
        reference = serializer.validated_data.get('reference', f'FOLO-{uuid.uuid4().hex[:8].upper()}')

        # Get wallet and beneficiary from serializer
        from_wallet = serializer.wallet
        beneficiary = serializer.beneficiary
        user = request.user

        # Update beneficiary last_used timestamp
        beneficiary.last_used = timezone.now()
        beneficiary.save(update_fields=['last_used'])

        # Generate unique ID for the transaction
        external_unique_id = uuid.uuid4()
        
        # Determine transaction type for database
        if beneficiary.bank_code == "0052":
            transaction_type = 'WALLET_TO_IFT'
        elif transfer_type == 'PESALINK':
            transaction_type = 'WALLET_TO_PESALINK'
        else:
            transaction_type = 'WALLET_TO_BANK'

        # Create Transaction record initially as PENDING
        transaction = Transaction.objects.create(
            external_unique_id=external_unique_id,
            transaction_type=transaction_type,
            amount=amount,
            from_wallet=from_wallet,
            to_wallet=None,  # Bank transfers don't have destination wallet
            currency=from_wallet.currency,
            status='PENDING',
            user=user,
            customer=from_wallet.customer,
            description=description,
            reference=reference,
            bank_beneficiary=beneficiary
        )

        # Always use standard DTB service (SCA JWT handling moved to /sca/upgrade-jwt/ endpoint)
        dtb_service = DTBService()

        callback_url = settings.BANK_TRANSFER_CALLBACK_URL

        # Check if this is a DTB bank transfer (bank code "0052") - use IFT
        if beneficiary.bank_code == "0052":
            payload = create_ift_payload(
                account_name=beneficiary.account_holder_name,
                account_number=beneficiary.account_number,
                branch_code=beneficiary.branch_code,
                amount=amount,
                callback_url=callback_url,
                description=description,
                external_unique_id=external_unique_id
            )
        # Prepare payload using canonical key ordering
        elif transfer_type == 'PESALINK':
            payload = create_pesalink_payload(
                amount=amount,
                description=description,
                external_unique_id=external_unique_id,
                account_number=beneficiary.account_number,
                branch_code=beneficiary.branch_code,
                bank_code=beneficiary.bank_code,
                reference=reference,
                callback_url=callback_url
            )
        else:  # EFT
            payload = create_eft_payload(
                account_name=beneficiary.account_holder_name,
                account_number=beneficiary.account_number,
                branch_code=beneficiary.branch_code,
                bank_code=beneficiary.bank_code,
                amount=amount,
                callback_url=callback_url,
                description=description,
                external_unique_id=external_unique_id,
                reference=reference
            )

        try:
            if beneficiary.bank_code == "0052":
                response = dtb_service.wallet_to_ift_transfer(from_wallet.wallet_id, payload)
            elif transfer_type == 'PESALINK':
                response = dtb_service.wallet_to_pesalink_transfer(from_wallet.wallet_id, payload)
            else:
                response = dtb_service.wallet_to_eft_transfer(from_wallet.wallet_id, payload)

            # Save tracing context if present
            if 'tracingContext' in response:
                transaction.tracing_context = response.get('tracingContext')

            # Update transaction based on response
            if response.get('status') in ['SUCCESSFUL', 'PENDING']:
                transaction.status = response.get('status')
                transaction.withdrawal_id = response.get('withdrawalId')
                transaction.gateway = response.get('gateway')
                transaction.gateway_transaction_id = response.get('gatewayTransactionId')
                transaction.fee = response.get('fee', 0)
                
                # Parse extra_info if it's a JSON string, otherwise use as-is
                extra_info = response.get('extraInfo')
                if extra_info:
                    if isinstance(extra_info, str):
                        import json
                        try:
                            transaction.extra_info = json.loads(extra_info)
                        except json.JSONDecodeError:
                            transaction.extra_info = {'raw': extra_info}
                    else:
                        transaction.extra_info = extra_info
                
                transaction.save()

                # Schedule timeout check for this transaction (5 minutes)
                schedule_transaction_timeout_check.delay(
                    str(transaction.transaction_id),
                    'wallet_transaction',
                    5  # 5 minutes timeout
                )

                # Update wallet balance
                wallet_details = dtb_service.get_wallet_details(from_wallet.wallet_id)
                from_wallet.available_balance = wallet_details['availableBalance']
                from_wallet.current_balance = wallet_details['currentBalance']
                from_wallet.save()

                # Determine transfer type for messaging
                display_transfer_type = "IFT" if beneficiary.bank_code == "0052" else transfer_type

                status_message = f"{display_transfer_type} transfer initiated successfully"
                if response.get('status') == 'PENDING':
                    status_message = f"{display_transfer_type} transfer is being processed"

                return Response({
                    "message": status_message,
                    "transaction_id": str(transaction.transaction_id),
                    "withdrawal_id": transaction.withdrawal_id,
                    "amount": float(amount),
                    "fee": float(transaction.fee),
                    "status": transaction.status,
                    "transfer_type": transfer_type,
                    "beneficiary": {
                        "account_holder_name": beneficiary.account_holder_name,
                        "account_number": beneficiary.account_number,
                        "bank_name": beneficiary.bank_name,
                        "nickname": beneficiary.nickname
                    }
                }, status=status.HTTP_200_OK)
            else:
                # Handle failed transaction initiation
                transaction.status = 'FAILED'
                
                # Parse extra_info if it's a JSON string
                extra_info = response.get('extraInfo')
                if extra_info:
                    if isinstance(extra_info, str):
                        import json
                        try:
                            transaction.extra_info = json.loads(extra_info)
                        except json.JSONDecodeError:
                            transaction.extra_info = {'raw': extra_info}
                    else:
                        transaction.extra_info = extra_info
                
                transaction.save()
                logger.error(f"DTB {transfer_type} Transfer initiation failed for transaction {transaction.transaction_id}: {response}")
                return Response({
                    "error": f"{transfer_type} transfer initiation failed",
                    "transaction_id": str(transaction.transaction_id),
                    "status": response.get('status'),
                    "details": response.get('extraInfo', response)
                }, status=status.HTTP_400_BAD_REQUEST)

        except DTBServiceSCAChallengeError as e:
            # Handle SCA challenge - save SCA session for later retry
            logger.info(f"SCA challenge detected for bank transfer: {e}")

            # Save SCA session for later retry
            from ..models import SCASession

            # Add wallet ID to payload for retry
            payload_with_wallet = payload.copy()
            payload_with_wallet['walletId'] = from_wallet.wallet_id

            SCASession.objects.create(
                user=request.user,
                transaction=transaction,
                intent_id=e.sca_challenge['intent_id'],
                sca_type=e.sca_challenge['sca_type'],
                transfer_type=transaction_type,
                transfer_payload=payload_with_wallet,
                original_dtb_jwt=dtb_service.jwt_token,  # Store the JWT that was used for the original request
                expires_at=timezone.now() + timezone.timedelta(minutes=5)
            )

            return Response({
                "error": "SCA challenge required",
                "sca_challenge": e.sca_challenge,
                "transaction_id": str(transaction.transaction_id),
                "message": "Please complete OTP verification to proceed"
            }, status=status.HTTP_403_FORBIDDEN)

        except (DTBServiceAuthenticationError, DTBServiceAPIError) as e:
            transaction.status = 'FAILED'
            transaction.save()
            error_message = str(e)
            logger.error(f"DTB API Error during {transfer_type} transfer for transaction {transaction.transaction_id}: {e}")
            return Response({
                "error": error_message,
                "transaction_id": str(transaction.transaction_id)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            # Handle unexpected errors
            transaction.status = 'FAILED'
            transaction.save()
            logger.error(f"Unexpected error during {transfer_type} transfer for transaction {transaction.transaction_id}: {e}")
            return Response({
                "error": "An unexpected error occurred",
                "transaction_id": str(transaction.transaction_id)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BankTransferWebhookAPIView(APIView):
    """
    Webhook endpoint for bank transfer status updates.
    This handles callbacks for both PesaLink and EFT transfers.
    """
    permission_classes = []  # Allow unauthenticated access for webhook callbacks
    def post(self, request):
        data = request.data
        external_unique_id = data.get('externalUniqueId')
        status_value = data.get('status')
        
        logger.info(f"Bank transfer webhook received: {data}")
        
        try:
            # Find the transaction by external_unique_id
            transaction = Transaction.objects.get(
                external_unique_id=uuid.UUID(external_unique_id),
                transaction_type__in=['WALLET_TO_BANK', 'WALLET_TO_PESALINK']
            )
            
            # Store the complete webhook response data
            transaction.webhook_response = data
            
            # Store old status for event emission
            old_status = transaction.status
            
            # Update transaction status
            transaction.status = 'SUCCESSFUL' if status_value == 'SUCCESSFUL' else 'FAILED'
            new_status = transaction.status
            
            # Update other fields from webhook
            if data.get('withdrawalId'):
                transaction.withdrawal_id = data.get('withdrawalId')
            
            if data.get('fee') is not None:
                transaction.fee = data.get('fee')
            
            # Update gateway fields directly
            if data.get('gateway'):
                transaction.gateway = data.get('gateway')
            
            if data.get('gatewayTransactionId'):
                transaction.gateway_transaction_id = data.get('gatewayTransactionId')
            
            # Store additional fields in extra_info
            # Ensure extra_info is a dict, not a string
            if not transaction.extra_info or not isinstance(transaction.extra_info, dict):
                transaction.extra_info = {}
            
            transaction.extra_info.update({
                'paymentType': data.get('paymentType'),
                'created': data.get('created'),
                'errorDescription': data.get('errorDescription', '')
            })
            
            transaction.save()
            
            # If transaction is successful, update wallet balance
            if status_value == 'SUCCESSFUL':
                dtb_service = DTBService()
                wallet_details = dtb_service.get_wallet_details(transaction.from_wallet.wallet_id)
                wallet = transaction.from_wallet
                wallet.available_balance = wallet_details['availableBalance']
                wallet.current_balance = wallet_details['currentBalance']
                wallet.save()
                
            # Emit transaction status change event if status changed
            if old_status != new_status:
                self._emit_transaction_event(transaction, old_status, new_status)
                
            return Response({"message": "Webhook processed successfully"}, status=status.HTTP_200_OK)
        
        except Transaction.DoesNotExist:
            logger.error(f"Webhook received for unknown bank transfer transaction: {external_unique_id}")
            return Response({"error": "Transaction not found"}, status=status.HTTP_404_NOT_FOUND)
        
        except Exception as e:
            logger.error(f"Error processing bank transfer webhook: {e}")
            return Response({"error": "An unexpected error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _emit_transaction_event(self, transaction, old_status, new_status):
        """Helper method to emit a transaction status change event."""
        logger.info(f"Bank transfer {transaction.transaction_id} status changed from {old_status} to {new_status}")
        # Add your event emission logic here (WebSocket, Push notification, etc.)


class GetBankTransferFeeAPIView(APIView):
    """API for getting the fee for a bank transfer."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        serializer = BankTransferFeeRequestSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Get the user's active wallet
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
        transfer_type = serializer.validated_data['transfer_type']
        
        # Map our transfer types to DTB types
        dtb_type = "KE_DTB_PESALINK" if transfer_type == 'PESALINK' else "KE_DTB_EFT"
        
        try:
            dtb_service = DTBService()
            fee_response = dtb_service.get_bank_transfer_fee(wallet.wallet_id, amount, dtb_type)
            
            # Add transfer type to response
            fee_response['transfer_type'] = transfer_type
            
            # Use our response serializer to return a cleaner format
            response_serializer = BankTransferFeeResponseSerializer(fee_response)
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        except (DTBServiceAuthenticationError, DTBServiceAPIError) as e:
            logger.error(f"DTB API Error getting bank transfer fee: {e}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Unexpected error getting bank transfer fee: {e}")
            return Response({"error": "An unexpected error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
