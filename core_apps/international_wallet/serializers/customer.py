from rest_framework import serializers
from django.contrib.auth import get_user_model
from core_apps.international_wallet.models.customer import Customer

User = get_user_model()


class _UserForCustomerSerializer(serializers.ModelSerializer):
    """
    A simple, read-only serializer for displaying user details.
    """

    class Meta:
        model = User
        fields = ['id', 'username', 'mobile', 'email']


class CustomerSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for the Customer model.
    """
    user = _UserForCustomerSerializer(read_only=True)

    class Meta:
        model = Customer
        fields = [
            'id',
            'customer_id',
            'current_status',
            'provider',
            'signed_agreement_id',
            'user',
            'created_on',
            'updated_on'
        ]
        read_only_fields = fields  # Make all fields read-only
