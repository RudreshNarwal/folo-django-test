import logging
from django.db import transaction as db_transaction
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from ..models import SCASession, Transaction
from ..services.sca_service import SCAService, SCAServiceError
from ..services.dtb_services import (
    DTBService,
    DTBServiceError,
    DTBServiceAuthenticationError,
    DTBServiceAPIError,
    DTBServiceSCAChallengeError,
)
from ..serializers import SCAUpgradeSerializer

logger = logging.getLogger(__name__)


class SCAUpgradeJWTAPIView(APIView):
    """
    API endpoint for upgrading JWT with SCA credentials.
    Handles OTP verification, JWT upgrade, AND automatic transfer retry.
    """
    permission_classes = [IsAuthenticated]

    @db_transaction.atomic
    def post(self, request):
        """
        Upgrade JWT using intent_id and OTP, then retry the original transfer.

        Request body:
        {
            "intent_id": "84b479c1edaa44d8b15a473614a24438",
            "otp": "911911"
        }

        Returns: Complete transfer result (not just JWT)
        """
        # Accept both intent_id and intentId from clients
        data = request.data.copy()
        if 'intent_id' not in data and 'intentId' in data:
            data['intent_id'] = data['intentId']

        serializer = SCAUpgradeSerializer(data=data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        intent_id = serializer.validated_data['intent_id']
        otp = serializer.validated_data['otp']

        try:
            # 1. Get SCA session
            sca_session = SCASession.objects.get(
                intent_id=intent_id,
                user=request.user,
                status='PENDING'
            )

            # 2. Get current JWT from a new DTB service instance
            # The DTB API needs the current JWT to know which session to upgrade
            dtb_service_temp = DTBService()
            current_jwt = dtb_service_temp.jwt_token

            # 3. Upgrade DTB JWT with current JWT context
            # This calls the /authentication/upgrade-jwt endpoint with Authorization header
            sca_service = SCAService()
            jwt_data = sca_service.upgrade_jwt(intent_id, otp, current_jwt=current_jwt)
            upgraded_jwt = jwt_data['jwt_token']

            # 4. Create DTB service with upgraded JWT
            dtb_service = DTBService()
            dtb_service.jwt_token = upgraded_jwt
            dtb_service.headers['Authorization'] = f'Bearer {upgraded_jwt}'

            # 5. Retry original transfer based on type
            transaction = sca_session.transaction
            payload = sca_session.transfer_payload

            if sca_session.transfer_type == 'WALLET_TO_WALLET':
                response_code = dtb_service.wallet_to_wallet_transfer(payload)

                if response_code == 204:
                    transaction.status = 'SUCCESSFUL'
                    transaction.save()

                    # Update wallet balance
                    wallet_details = dtb_service.get_wallet_details(payload['fromWalletId'])
                    from_wallet = transaction.from_wallet
                    from_wallet.available_balance = wallet_details['availableBalance']
                    from_wallet.current_balance = wallet_details['currentBalance']
                    from_wallet.save()

                    # Mark SCA session as completed
                    sca_session.status = 'COMPLETED'
                    sca_session.save()

                    return Response({
                        "message": "Transfer completed successfully",
                        "transaction_id": str(transaction.transaction_id),
                        "from_wallet": payload['fromWalletId'],
                        "to_wallet": payload['toWalletId'],
                        "amount": payload['amount'],
                        "status": transaction.status
                    }, status=status.HTTP_200_OK)
                else:
                    transaction.status = 'FAILED'
                    transaction.save()
                    sca_session.status = 'FAILED'
                    sca_session.save()

                    return Response({
                        "error": f"Transfer failed with response code: {response_code}",
                        "transaction_id": str(transaction.transaction_id)
                    }, status=status.HTTP_400_BAD_REQUEST)

            elif sca_session.transfer_type == 'WALLET_TO_MPESA':
                wallet_id = payload.get('walletId')
                mpesa_payload = {k: v for k, v in payload.items() if k != 'walletId'}

                response = dtb_service.wallet_to_mpesa_transfer(wallet_id, mpesa_payload)

                if response.get('status') in ['SUCCESSFUL', 'PENDING']:
                    transaction.status = response.get('status')
                    transaction.withdrawal_id = response.get('withdrawalId')
                    transaction.gateway = response.get('gateway')
                    transaction.gateway_transaction_id = response.get('gatewayTransactionId')
                    transaction.fee = response.get('fee', 0)

                    if not transaction.extra_info:
                        transaction.extra_info = {}
                    transaction.extra_info['initiation_response'] = response.get('extraInfo')
                    transaction.save()

                    # Update wallet balance
                    wallet_details = dtb_service.get_wallet_details(wallet_id)
                    from_wallet = transaction.from_wallet
                    from_wallet.available_balance = wallet_details['availableBalance']
                    from_wallet.current_balance = wallet_details['currentBalance']
                    from_wallet.save()

                    # Mark SCA session as completed
                    sca_session.status = 'COMPLETED'
                    sca_session.save()

                    return Response({
                        "message": "MPESA withdrawal initiated successfully" if response.get('status') == 'SUCCESSFUL'
                                  else "MPESA withdrawal is being processed",
                        "transaction_id": str(transaction.transaction_id),
                        "withdrawal_id": transaction.withdrawal_id,
                        "amount": mpesa_payload['amount'],
                        "fee": float(transaction.fee),
                        "status": transaction.status
                    }, status=status.HTTP_200_OK)
                else:
                    transaction.status = 'FAILED'
                    if not transaction.extra_info:
                        transaction.extra_info = {}
                    if 'extraInfo' in response:
                        transaction.extra_info['initiation_response'] = response.get('extraInfo')
                    transaction.save()

                    sca_session.status = 'FAILED'
                    sca_session.save()

                    return Response({
                        "error": "MPESA withdrawal initiation failed",
                        "transaction_id": str(transaction.transaction_id),
                        "status": response.get('status'),
                        "details": response.get('extraInfo', response)
                    }, status=status.HTTP_400_BAD_REQUEST)

            elif sca_session.transfer_type in ['WALLET_TO_PESALINK', 'WALLET_TO_BANK']:
                wallet_id = payload.get('walletId')
                bank_payload = {k: v for k, v in payload.items() if k != 'walletId'}

                if sca_session.transfer_type == 'WALLET_TO_PESALINK':
                    response = dtb_service.wallet_to_pesalink_transfer(wallet_id, bank_payload)
                else:
                    response = dtb_service.wallet_to_eft_transfer(wallet_id, bank_payload)

                if response.get('status') in ['SUCCESSFUL', 'PENDING']:
                    transaction.status = response.get('status')
                    transaction.withdrawal_id = response.get('withdrawalId')
                    transaction.gateway = response.get('gateway')
                    transaction.gateway_transaction_id = response.get('gatewayTransactionId')
                    transaction.fee = response.get('fee', 0)
                    transaction.extra_info = response.get('extraInfo')
                    transaction.save()

                    # Update wallet balance
                    wallet_details = dtb_service.get_wallet_details(wallet_id)
                    from_wallet = transaction.from_wallet
                    from_wallet.available_balance = wallet_details['availableBalance']
                    from_wallet.current_balance = wallet_details['currentBalance']
                    from_wallet.save()

                    # Mark SCA session as completed
                    sca_session.status = 'COMPLETED'
                    sca_session.save()

                    transfer_type_display = "PesaLink" if sca_session.transfer_type == 'WALLET_TO_PESALINK' else "EFT"
                    return Response({
                        "message": f"{transfer_type_display} transfer initiated successfully",
                        "transaction_id": str(transaction.transaction_id),
                        "withdrawal_id": transaction.withdrawal_id,
                        "amount": bank_payload['amount'],
                        "fee": float(transaction.fee),
                        "status": transaction.status,
                        "transfer_type": transfer_type_display
                    }, status=status.HTTP_200_OK)
                else:
                    transaction.status = 'FAILED'
                    if 'extraInfo' in response:
                        transaction.extra_info = response.get('extraInfo')
                    transaction.save()

                    sca_session.status = 'FAILED'
                    sca_session.save()

                    return Response({
                        "error": f"{sca_session.transfer_type} transfer initiation failed",
                        "transaction_id": str(transaction.transaction_id),
                        "status": response.get('status'),
                        "details": response.get('extraInfo', response)
                    }, status=status.HTTP_400_BAD_REQUEST)

        except SCASession.DoesNotExist:
            logger.error(f"SCA session not found for intent_id: {intent_id}")
            return Response({
                "error": "Invalid or expired SCA session",
                "details": "SCA session not found or already completed"
            }, status=status.HTTP_404_NOT_FOUND)

        except SCAServiceError as e:
            logger.error(f"SCA JWT upgrade failed: {e}")
            if sca_session:
                sca_session.status = 'FAILED'
                sca_session.save()
            return Response({
                "error": "JWT upgrade failed",
                "details": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

        except (DTBServiceAuthenticationError, DTBServiceAPIError) as e:
            logger.error(f"DTB API Error during SCA retry: {e}")
            if transaction:
                transaction.status = 'FAILED'
                transaction.save()
            if sca_session:
                sca_session.status = 'FAILED'
                sca_session.save()
            return Response({
                "error": str(e),
                "transaction_id": str(transaction.transaction_id) if transaction else None
            }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"Unexpected error during SCA JWT upgrade: {e}")
            if transaction:
                transaction.status = 'FAILED'
                transaction.save()
            if sca_session:
                sca_session.status = 'FAILED'
                sca_session.save()
            return Response({
                "error": "An unexpected error occurred",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
