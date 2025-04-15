import logging
import uuid
from django.conf import settings
from django.db import transaction as db_transaction
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status, generics

from ..models import Transaction, Wallet, CustomerProfile
from ..serializers import (
    TransactionSerializer, 
    WalletToWalletTransferSerializer,
    WalletToMpesaTransferSerializer,
    WithdrawalFeeRequestSerializer,
    WithdrawalFeeResponseSerializer
)
from ..services.dtb_services import (
    DTBService,
    DTBServiceError,
    DTBServiceAuthenticationError,
    DTBServiceAPIError,
)

logger = logging.getLogger(__name__)


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
    """API view for wallet-to-MPESA transfers."""
    permission_classes = [IsAuthenticated]
    
    @db_transaction.atomic
    def post(self, request):
        # Pass request context to the serializer for user authentication
        serializer = WalletToMpesaTransferSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Get validated data
        amount = serializer.validated_data['amount']
        deliver_to_phone = serializer.validated_data['deliver_to_phone']
        reference = serializer.validated_data.get('reference', f"REF-{uuid.uuid4().hex[:8]}")
        description = serializer.validated_data.get('description', 'Wallet to MPESA transfer')
        
        # Get wallet from serializer (already validated in serializer)
        wallet = serializer.wallet
        wallet_id = wallet.wallet_id
        
        # Generate unique ID for the transaction
        external_unique_id = uuid.uuid4()
        
        # Create Transaction record initially as PENDING
        transaction = Transaction.objects.create(
            external_unique_id=external_unique_id,
            transaction_type='WALLET_TO_MPESA',
            amount=amount,
            from_wallet=wallet,
            currency=wallet.currency,
            status='PENDING',
            user=request.user,
            customer=wallet.customer,
            description=description,
            deliver_to_phone=deliver_to_phone,
            reference=reference
        )
        
        # Prepare payload for DTB service
        callback_url = settings.WALLET_WITHDRAWAL_CALLBACK_URL
        payload = {
            "deliverToPhone": deliver_to_phone,
            "reference": reference,
            "amount": float(amount),
            "callbackUrl": callback_url,
            "description": description,
            "type": "KE_DTB_MPESA",
            "externalUniqueId": str(external_unique_id)
        }
        
        # Call DTB service
        dtb_service = DTBService()
        try:
            response = dtb_service.wallet_to_mpesa_transfer(wallet_id, payload)
            
            # Update transaction record with response data
            if response.get('status') == 'SUCCESSFUL':
                transaction.status = 'SUCCESSFUL'
                transaction.withdrawal_id = response.get('withdrawalId')
                transaction.gateway = response.get('gateway')
                transaction.gateway_transaction_id = response.get('gatewayTransactionId')
                transaction.fee = response.get('fee', 0)
                transaction.extra_info = response.get('extraInfo')
                transaction.save()
                
                # Update wallet balance (fetch latest)
                wallet_details = dtb_service.get_wallet_details(wallet_id)
                wallet.available_balance = wallet_details['availableBalance']
                wallet.current_balance = wallet_details['currentBalance']
                wallet.save()
                
                # Return success response
                return Response({
                    "message": "MPESA withdrawal completed successfully",
                    "transaction_id": str(transaction.transaction_id),
                    "withdrawal_id": transaction.withdrawal_id,
                    "amount": float(amount),
                    "fee": float(transaction.fee),
                    "status": transaction.status,
                    "gateway_transaction_id": transaction.gateway_transaction_id
                }, status=status.HTTP_200_OK)
            else:
                # Handle failed transaction
                transaction.status = 'FAILED'
                if 'extraInfo' in response:
                    transaction.extra_info = response.get('extraInfo')
                transaction.save()
                
                return Response({
                    "error": "MPESA withdrawal failed",
                    "transaction_id": str(transaction.transaction_id),
                    "status": response.get('status'),
                    "details": response
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except (DTBServiceAuthenticationError, DTBServiceAPIError) as e:
            # Handle API errors
            transaction.status = 'FAILED'
            transaction.save()
            logger.error(f"DTB API Error during wallet-to-MPESA transfer: {e}")
            return Response({
                "error": str(e),
                "transaction_id": str(transaction.transaction_id)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            # Handle unexpected errors
            transaction.status = 'FAILED'
            transaction.save()
            logger.error(f"Unexpected error during wallet-to-MPESA transfer: {e}")
            return Response({
                "error": "An unexpected error occurred",
                "transaction_id": str(transaction.transaction_id)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
