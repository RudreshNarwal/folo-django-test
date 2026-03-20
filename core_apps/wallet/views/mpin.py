import logging
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from ..models import Wallet
from ..serializers import UpdateMpinSerializer

logger = logging.getLogger(__name__)


class UpdateWalletMpinAPIView(APIView):
    """API endpoint for updating a wallet's MPIN."""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        # Get the user's active wallet
        try:
            wallet = Wallet.objects.get(user=request.user, status='ACTIVE')
        except Wallet.DoesNotExist:
            return Response(
                {"error": "No active wallet found for your account"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Wallet.MultipleObjectsReturned:
            # If multiple active wallets exist, get the primary wallet or the first one
            wallets = Wallet.objects.filter(user=request.user, status='ACTIVE')
            wallet = wallets.first()  # Get the first active wallet
        
        # Add wallet_id to the request data
        request_data = request.data.copy()
        request_data['wallet_id'] = wallet.wallet_id
        
        serializer = UpdateMpinSerializer(data=request_data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        new_mpin = serializer.validated_data['new_mpin']
        
        # Update the MPIN
        is_new_mpin = wallet.mpin is None or wallet.mpin == ''
        wallet.mpin = new_mpin
        wallet.save()
        
        return Response({
            "message": "MPIN set successfully" if is_new_mpin else "MPIN updated successfully",
            "wallet_id": wallet.wallet_id,
            "has_mpin": True
        }, status=status.HTTP_200_OK)
