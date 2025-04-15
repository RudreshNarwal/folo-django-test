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
        serializer = UpdateMpinSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        wallet_id = serializer.validated_data['wallet_id']
        new_mpin = serializer.validated_data['new_mpin']
        
        try:
            wallet = Wallet.objects.get(wallet_id=wallet_id)
            
            # Check if the wallet belongs to the user
            if wallet.user != request.user:
                return Response(
                    {"error": "You do not have permission to update this wallet's MPIN"},
                    status=status.HTTP_403_FORBIDDEN
                )
                
            # Update the MPIN
            is_new_mpin = wallet.mpin is None or wallet.mpin == ''
            wallet.mpin = new_mpin
            wallet.save()
            
            return Response({
                "message": "MPIN set successfully" if is_new_mpin else "MPIN updated successfully",
                "wallet_id": wallet_id,
                "has_mpin": True
            }, status=status.HTTP_200_OK)
            
        except Wallet.DoesNotExist:
            return Response(
                {"error": "Wallet not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
