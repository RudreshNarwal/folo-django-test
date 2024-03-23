from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import Transaction
from .serializers import TransactionCreateSerializer
from .services import get_access_token


class InitiateTransactionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = TransactionCreateSerializer(data=request.data)
        if serializer.is_valid():
            # The amount is included in the serializer and will be part of the serializer.save()
            transaction = serializer.save(
                user=request.user,
                status='Initiated'
            )
            
            # Use the utility function to get the access token
            access_token, error = get_access_token()
            if error:
                transaction.status = 'Failed'
                transaction.response = {"error": error}
                transaction.save(update_fields=['status', 'response'])
                return Response({"error": "Failed to retrieve access token", "details": str(error)},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            return Response(
                {"message": "Transaction initiated successfully.", "transaction_id": transaction.id, "access_token": access_token},
                status=status.HTTP_201_CREATED)
            
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
