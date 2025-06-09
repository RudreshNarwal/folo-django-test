from rest_framework import serializers

from core_apps.common.services import get_image_data_uri_from_signed_url
from core_apps.international_wallet.constants import get_country_name_from_code
from core_apps.users.models.user import Address
from core_apps.users.utils import generate_presigned_url


class ResidentialAddressSerializer(serializers.ModelSerializer):
    """
    Serializer for the residential_address nested field within customer creation.
    """
    street_line_1 = serializers.CharField(source='line1')
    subdivision = serializers.CharField(source='state') # State or province
    postal_code = serializers.CharField(source='code')

    class Meta:
        model = Address
        fields = (
            "street_line_1", "city", "subdivision", "postal_code", "country"
        )


class CreateCustomerSerializer(serializers.Serializer):
    """
    Serializer for the create_customer_api endpoint.
    Validates all required fields for customer creation.
    """
    def validate(self, data):
        """
        Custom validation to ensure that all data is present and valid.
        """
        # Ensure the request context is available
        request_user = self.context.get("request").user
        user_country_code = request_user.country.code

        if not request_user.is_mobile_verified:
            raise serializers.ValidationError("User's mobile number must be verified to create a customer.")

        first_name = request_user.first_name
        last_name = request_user.last_name
        if not first_name or not last_name:
            raise serializers.ValidationError("User must have a first and last name to create a customer.")

        email = request_user.email
        if not request_user.email:
            raise serializers.ValidationError("User must have an email address to create a customer.")

        address = request_user.address if hasattr(request_user, 'address') else None
        if not address:
            raise serializers.ValidationError("User must have a address to create a customer.")

        dob = request_user.dob
        if not dob:
            raise serializers.ValidationError("User must have a date of birth to create a customer.")

        bridge_signed_agreement_id = request_user.bridge_signed_agreement_id
        if not bridge_signed_agreement_id:
            raise serializers.ValidationError("User must have signed the Bridge terms of service to create a customer.")

        ssn = request_user.documents.filter(document_type='SOCIAL_SECURITY_NUMBER').first()
        if not ssn:
            raise serializers.ValidationError("User must have a social security number document to create a customer.")

        dl_front = request_user.documents.filter(document_type='DRIVERS_LICENSE').first()
        if not dl_front:
            raise serializers.ValidationError("User must have a drivers license front document to create a customer.")

        dl_back = request_user.documents.filter(document_type='BACK_OF_DRIVERS_LICENSE').first()
        if not dl_back:
            raise serializers.ValidationError("User must have a drivers license back document to create a customer.")

        data["type"] = "individual"
        data["first_name"] = first_name
        data["last_name"] = last_name
        data["email"] = email
        data["residential_address"] = ResidentialAddressSerializer(address).data
        data["birth_date"] = dob.strftime("%Y-%m-%d")
        data["signed_agreement_id"] = bridge_signed_agreement_id
        country_name = get_country_name_from_code(user_country_code)
        data["identifying_information"] = [
            {
                "type": "ssn",
                "issuing_country": country_name,
                "number": ssn.document_number
            },
            {
                "type": "drivers_license",
                "issuing_country": country_name,
                "number": dl_front.document_number,
                "image_front": get_image_data_uri_from_signed_url(generate_presigned_url(dl_front.s3_key)),
                "image_back": get_image_data_uri_from_signed_url(generate_presigned_url(dl_back.s3_key))
            }
        ]

        return data


class DestinationSerializer(serializers.Serializer):
    """
    Serializer for the destination nested field within transfer initiation.
    """
    payment_rail = serializers.CharField(max_length=50) # e.g., "wire", "ach"
    currency = serializers.CharField(max_length=10) # e.g., "usd"
    external_account_id = serializers.CharField(max_length=255, help_text="ID of the registered external bank account.")


class InitiateTransferSerializer(serializers.Serializer):
    """
    Serializer for the initiate_transfer_api endpoint.
    Validates all required fields for transfer initiation.
    """
    amount = serializers.CharField(max_length=50, help_text="Amount as a string (important for decimals, e.g., '100.00').")
    on_behalf_of = serializers.CharField(max_length=255, help_text="The ID of the customer initiating the transfer.")
    source = serializers.DictField(required=False, help_text="Source details (can be empty if implied by from_address).")
    payment_rail = serializers.CharField(max_length=50, help_text="Source payment rail (e.g., 'polygon', 'ethereum').")
    currency = serializers.CharField(max_length=10, help_text="Currency of the source asset (e.g., 'usdc', 'eth').")
    from_address = serializers.CharField(max_length=255, required=False, allow_blank=True, help_text="Source crypto address for crypto-to-fiat.")
    destination = DestinationSerializer() # Nested serializer
