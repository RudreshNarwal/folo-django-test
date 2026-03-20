from rest_framework import serializers
from django.contrib.auth import get_user_model
from core_apps.international_wallet.models.external_bank_account import ExternalBankAccount
from core_apps.international_wallet.services.external_bank_account import decrypt_value

User = get_user_model()


class _UserForExternalBankAccountSerializer(serializers.ModelSerializer):
    """
    A simple, read-only serializer for displaying user details.
    """
    class Meta:
        model = User
        fields = ['id', 'username', 'mobile', 'email']


class ExternalBankAccountSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for the External Bank Account model.
    """
    user = _UserForExternalBankAccountSerializer(read_only=True)
    account_owner_name = serializers.CharField(
        read_only=True,
        help_text="Full name of the person who owns the account."
    )
    bank_name = serializers.CharField(
        read_only=True,
        help_text="The name of the financial institution."
    )
    account_name = serializers.CharField(
        read_only=True,
        help_text="Optional name for the account (e.g., 'Primary Checking', 'Holiday Savings')."
    )
    account_number = serializers.SerializerMethodField(
        read_only=True,
        help_text="Encrypted account number. Decrypt using the service layer."
    )
    iban = serializers.SerializerMethodField(
        read_only=True,
        help_text="Encrypted IBAN. Decrypt using the service layer."
    )
    swift_bic = serializers.SerializerMethodField(
        read_only=True,
        help_text="Encrypted SWIFT/BIC code. Decrypt using the service layer."
    )
    routing_number = serializers.SerializerMethodField(
        read_only=True,
        help_text="Encrypted routing number. Decrypt using the service layer."
    )
    customer_id = serializers.CharField(
        source='customer.id',
        read_only=True,
        help_text="The ID of the customer associated with this bank account."
    )
    currency = serializers.CharField(
        read_only=True,
        help_text="The currency of the bank account."
    )
    account_type = serializers.CharField(
        read_only=True,
        help_text="The type of the bank account (e.g., 'savings', 'checking')."
    )

    def get_account_number(self, obj):
        """
        Returns the decrypted account number.
        """
        return decrypt_value(obj.account_number_encrypted)

    def get_iban(self, obj):
        """
        Returns the decrypted IBAN.
        """
        return decrypt_value(obj.iban_encrypted)

    def get_swift_bic(self, obj):
        """
        Returns the decrypted SWIFT/BIC code.
        """
        return decrypt_value(obj.swift_bic_encrypted)

    def get_routing_number(self, obj):
        """
        Returns the decrypted routing number.
        """
        return decrypt_value(obj.routing_number_encrypted)

    class Meta:
        model = ExternalBankAccount
        fields = [
            'id',
            'customer_id',
            'account_owner_name',
            'bank_name',
            'account_name',
            'account_number',
            'iban',
            'swift_bic',
            'routing_number',
            'currency',
            'account_type',
            'user',
            'created_on',
            'updated_on'
        ]
        read_only_fields = fields  # Make all fields read-only
