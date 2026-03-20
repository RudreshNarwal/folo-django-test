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


class CustomerWalletDetailsSerializer(serializers.Serializer):
    """
        Serializer for the customer_wallet_detail_api endpoint.
        Validates all required fields for get customer wallet details.
    """

    def validate(self, data):
        """
        Custom validation to ensure that all data is present and valid.
        """
        # Ensure the request context is available
        request_user = self.context.get("request").user

        try:
            customer = Customer.objects.get(
                user=request_user,
                provider='BRIDGE',
            )
        except Customer.DoesNotExist:
            customer = None

        if not customer:
            raise serializers.ValidationError("International customer not found for this user.")

        customer_id = customer.customer_id
        if not customer_id:
            raise serializers.ValidationError("International customer does not onboarded yet.")

        if customer.current_status != 'ACTIVE':
            raise serializers.ValidationError("International customer is not active for wallet configuration.")

        wallet_address = customer.wallet_address
        if wallet_address is None or wallet_address == "":
            raise serializers.ValidationError("International customer wallet not created.")

        data["customer_id"] = customer_id
        data["waller_address"] = wallet_address
        return data
