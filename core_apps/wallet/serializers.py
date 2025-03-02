from rest_framework import serializers
from django.contrib.auth import get_user_model
from django_countries.serializers import CountryFieldMixin
from .models import CustomerProfile, ProviderDocument, TopUpTransaction, Wallet

User = get_user_model()

class UserSerializer(serializers.ModelSerializer, CountryFieldMixin):
    class Meta:
        model = User
        fields = [
            'id', 'mobile', 'first_name', 'last_name', 'email',
            'dob', 'gender', 'country_code', 'nation_id', 'city', 'country'
        ]

class CustomerProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer()

    class Meta:
        model = CustomerProfile
        fields = [
            'id', 'user', 'external_unique_id', 'kyc_status',
            'kyc_failure_stage', 'kyc_error_message'
        ]

class ProviderDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProviderDocument
        fields = ['provider_document_id']


class WalletResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = [
            "account_number", "available_balance", "configuration", "created",
            "currency", "current_balance", "customer_id", "description",
            "external_unique_id", "friendly_id", "name", "organisation_id",
            "reservations", "status", "wallet_id", "wallet_type_id"
        ]
        
class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = [
            'wallet_id', 'name', 'description', 'status', 'currency',
            'available_balance', 'current_balance'
        ]

class TopUpTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TopUpTransaction
        fields = [
            'payment_id', 'status', 'amount', 'currency', 'created_at', 'description',
        ]