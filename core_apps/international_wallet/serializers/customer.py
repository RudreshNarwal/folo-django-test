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
        fields = ['id', 'username', 'email', 'pkid', 'mobile', 'pkid']


class CustomerSerializer(serializers.ModelSerializer):
    """
    Serializer for the Customer model.
    """
    # Use the nested serializer for read operations to show user details
    user = _UserForCustomerSerializer(read_only=True)

    # Allow writing the user ID for creation/association
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source='user', write_only=True
    )

    class Meta:
        model = Customer
        fields = [
            'id',
            'customer_id',
            'current_status',
            'provider',
            'signed_agreement_id',
            'user',  # for reading
            'user_id',  # for writing
            'created_on',
            'updated_on'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'user']
