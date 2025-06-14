from rest_framework import serializers
from django.contrib.auth import get_user_model
from core_apps.international_wallet.models.internationl_wallet import InternationalWalletTransaction

User = get_user_model()


class _UserForInternationalWalletTransactionSerializer(serializers.ModelSerializer):
    """
    A simple, read-only serializer for displaying user details.
    """
    class Meta:
        model = User
        fields = ['id', 'username', 'mobile', 'email']


class InternationalWalletTransactionSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for the External Bank Account model.
    """
    user = _UserForInternationalWalletTransactionSerializer(read_only=True)

    class Meta:
        model = InternationalWalletTransaction
        fields = [
            'id',
            'txn_date',
            'amount',
            'final_amount',
            'exchange_fee',
            'developer_fee',
            'gas_fee',
            'source_payment_rail',
            'source_currency',
            'destination_payment_rail',
            'destination_currency',
            'transaction_id',
            'client_reference_id',
            'state',
            'receipt_url',
            'user',
            'succeeded_at',
            'created_on',
            'updated_on'
        ]
        read_only_fields = fields  # Make all fields read-only
