import logging
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status, generics
from django.db import transaction as db_transaction
from rest_framework.exceptions import ValidationError

from ..models import BankBeneficiary
from ..serializers import (
    BankBeneficiarySerializer,
    CreateBankBeneficiarySerializer
)

logger = logging.getLogger(__name__)


class BankBeneficiaryListCreateAPIView(generics.ListCreateAPIView):
    """
    API view for listing and creating bank beneficiaries.
    GET: List all active beneficiaries for the user
    POST: Create a new beneficiary
    """
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateBankBeneficiarySerializer
        return BankBeneficiarySerializer
    
    def get_queryset(self):
        return BankBeneficiary.objects.filter(
            user=self.request.user, 
            is_active=True
        ).order_by('-last_used', '-created_at')
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class BankBeneficiaryDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """
    API view for retrieving, updating, and deleting a specific bank beneficiary.
    GET: Retrieve beneficiary details
    PUT/PATCH: Update beneficiary details
    DELETE: Soft delete (deactivate) beneficiary
    """
    permission_classes = [IsAuthenticated]
    serializer_class = BankBeneficiarySerializer
    
    def get_queryset(self):
        return BankBeneficiary.objects.filter(user=self.request.user)
    
    def perform_destroy(self, instance):
        # Check if user wants permanent deletion
        permanent_delete = self.request.query_params.get('permanent', 'false').lower() == 'true'
        
        if permanent_delete:
            # Check if beneficiary has any transactions
            if instance.transactions.exists():
                # Cannot permanently delete if there are linked transactions
                raise ValidationError({
                    "error": "Cannot permanently delete beneficiary with existing transactions. Use soft delete instead."
                })
            else:
                # Permanent delete if no transactions
                instance.delete()
        else:
            # Soft delete - just deactivate the beneficiary (default behavior)
            instance.is_active = False
            instance.save()


class RecentBankBeneficiariesAPIView(generics.ListAPIView):
    """
    API view for listing the user's 5 most recently used bank beneficiaries.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = BankBeneficiarySerializer
    
    def get_queryset(self):
        return BankBeneficiary.objects.filter(
            user=self.request.user,
            is_active=True,
            last_used__isnull=False
        ).order_by('-last_used')[:5]


class ActivateBankBeneficiaryAPIView(APIView):
    """
    API view for reactivating a deactivated bank beneficiary.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        try:
            beneficiary = BankBeneficiary.objects.get(
                id=pk, 
                user=request.user
            )
            beneficiary.is_active = True
            beneficiary.save()
            
            serializer = BankBeneficiarySerializer(beneficiary)
            return Response({
                "message": "Beneficiary activated successfully",
                "beneficiary": serializer.data
            }, status=status.HTTP_200_OK)
            
        except BankBeneficiary.DoesNotExist:
            return Response(
                {"error": "Beneficiary not found"}, 
                status=status.HTTP_404_NOT_FOUND
            ) 