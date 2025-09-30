import logging
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from ..services.sca_service import SCAService, SCAServiceError
from ..serializers import SCAUpgradeSerializer

logger = logging.getLogger(__name__)


class SCAUpgradeJWTAPIView(APIView):
    """
    API endpoint for upgrading JWT with SCA credentials.
    Handles OTP verification and JWT upgrade for DTB API calls.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Upgrade JWT using intent_id and OTP from SCA challenge.

        Request body:
        {
            "intent_id": "84b479c1edaa44d8b15a473614a24438",
            "otp": "911911"
        }
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
            sca_service = SCAService()
            jwt_data = sca_service.upgrade_jwt(intent_id, otp)

            # Align response with mobile client expectations
            return Response({
                "message": "JWT upgraded successfully",
                "upgraded_jwt": jwt_data['jwt_token'],
                "session_id": jwt_data.get('session_id'),
                "expires_at": jwt_data.get('expires_at')
            }, status=status.HTTP_200_OK)

        except SCAServiceError as e:
            logger.error(f"SCA JWT upgrade failed: {e}")
            return Response({
                "error": "JWT upgrade failed",
                "details": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Unexpected error during SCA JWT upgrade: {e}")
            return Response({
                "error": "An unexpected error occurred",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
