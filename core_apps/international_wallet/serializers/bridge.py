from rest_framework import serializers

from core_apps.common.services import get_image_data_uri_from_signed_url
from core_apps.international_wallet.models import Customer
from core_apps.users.models.user import Address
from core_apps.users.utils import generate_presigned_url


class ResidentialAddressSerializer(serializers.ModelSerializer):
    """
    Serializer for the residential_address nested field within customer creation.
    """
    street_line_1 = serializers.CharField(source='line1')
    street_line_2 = serializers.CharField(source='line2')
    postal_code = serializers.CharField(source='code')
    subdivision = serializers.SerializerMethodField()
    country = serializers.SerializerMethodField()

    def get_subdivision(self, obj):
        """
        Returns the state or province code from the address.
        """
        return obj.state_master.code

    def get_country(self, obj):
        """
        Returns the country code from the address.
        """
        return obj.country_master.code

    class Meta:
        model = Address
        fields = (
            "street_line_1", "street_line_2", "city", "subdivision", "postal_code", "country"
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

        try:
            customer = Customer.objects.get(
                user=request_user,
                provider='BRIDGE',
            )
        except Customer.DoesNotExist:
            customer = None

        if not customer:
            raise serializers.ValidationError("International customer not found for this user.")

        bridge_signed_agreement_id = customer.signed_agreement_id
        # Check if the user has already signed the Bridge terms of service
        if customer.current_status == 'ACTIVE':
            raise serializers.ValidationError("International customer already onboarded for this user.")

        address = request_user.address if hasattr(request_user, 'address') else None
        if not address:
            raise serializers.ValidationError("User must have a address to create a customer.")

        if (
                not address.line1 or not address.city or not address.code or not address.state_master_id or
                not address.country_master_id
        ):
            raise serializers.ValidationError(
                "User's address must have all required fields (line1, city, state, code, country) to create a customer."
            )

        # User country
        user_country_code = request_user.country_master.code

        # Validate that the user is verified and has all required fields
        if not request_user.is_mobile_verified:
            raise serializers.ValidationError("User's mobile number must be verified to create a customer.")

        first_name = request_user.first_name
        last_name = request_user.last_name
        if not first_name or not last_name:
            raise serializers.ValidationError("User must have a first and last name to create a customer.")

        email = request_user.email
        if not request_user.email:
            raise serializers.ValidationError("User must have an email address to create a customer.")

        phone = request_user.get_full_mobile
        if not phone:
            raise serializers.ValidationError("User must have a phone number to create a customer.")

        dob = request_user.dob
        if not dob:
            raise serializers.ValidationError("User must have a date of birth to create a customer.")

        data["type"] = "individual"
        data["first_name"] = first_name
        data["last_name"] = last_name
        data["email"] = email
        data["phone"] = phone
        data["residential_address"] = ResidentialAddressSerializer(address).data
        data["birth_date"] = dob.strftime("%Y-%m-%d")
        data["signed_agreement_id"] = bridge_signed_agreement_id
        if user_country_code == 'US':
            ssn = request_user.documents.filter(document_type='SOCIAL_SECURITY_NUMBER').first()
            if not ssn:
                raise serializers.ValidationError(
                    "User must have a social security number document to create a customer.")

            dl_front = request_user.documents.filter(document_type='DRIVERS_LICENSE').first()
            if not dl_front:
                raise serializers.ValidationError(
                    "User must have a drivers license front document to create a customer.")

            dl_back = request_user.documents.filter(document_type='BACK_OF_DRIVERS_LICENSE').first()
            if not dl_back:
                raise serializers.ValidationError(
                    "User must have a drivers license back document to create a customer.")

            data["identifying_information"] = [
                {
                    "type": "ssn",
                    "issuing_country": address.country_master.code,
                    "number": ssn.document_number
                },
                {
                    "type": "drivers_license",
                    "issuing_country": address.country_master.code,
                    "number": dl_front.document_number,
                    "image_front": get_image_data_uri_from_signed_url(generate_presigned_url(dl_front.s3_key)),
                    "image_back": get_image_data_uri_from_signed_url(generate_presigned_url(dl_back.s3_key))
                }
            ]
        else:
            passport_front = request_user.documents.filter(document_type='PASSPORT').first()
            if user_country_code != 'US' and not passport_front:
                raise serializers.ValidationError("User must have a passport front document to create a customer.")

            passport_back = request_user.documents.filter(document_type='BACK_OF_PASSPORT').first()
            if user_country_code != 'US' and not passport_back:
                raise serializers.ValidationError("User must have a passport back document to create a customer.")

            employment_status = request_user.employment_status
            if not employment_status:
                raise serializers.ValidationError("User must have an employment status to create a customer.")

            expected_monthly_payments = request_user.expected_monthly_payments
            if not expected_monthly_payments:
                raise serializers.ValidationError("User must have expected monthly payments to create a customer.")

            acting_as_intermediary = request_user.acting_as_intermediary
            if acting_as_intermediary is None:
                raise serializers.ValidationError("User must specify if they are acting as an intermediary.")

            most_recent_occupation = request_user.occupation
            if not most_recent_occupation:
                raise serializers.ValidationError("User must have an occupation to create a customer.")

            account_purpose = request_user.account_purpose
            account_purpose_other = request_user.account_purpose_other
            if not account_purpose and not account_purpose_other:
                raise serializers.ValidationError("User must have an account purpose to create a customer.")

            source_of_funds = request_user.source_of_funds
            if not source_of_funds:
                raise serializers.ValidationError("User must have a source of funds to create a customer.")

            data["employment_status"] = employment_status.lower()
            data["expected_monthly_payments"] = str(expected_monthly_payments)
            data["acting_as_intermediary"] = "yes" if acting_as_intermediary else "no"
            data["most_recent_occupation"] = most_recent_occupation.code
            data["account_purpose"] = account_purpose.lower()
            data["account_purpose_other"] = account_purpose_other
            data["source_of_funds"] = source_of_funds.lower()
            data["identifying_information"] = [
                {
                    "type": "passport",
                    "issuing_country": address.country_master.code,
                    "number": passport_front.document_number,
                    "image_front": get_image_data_uri_from_signed_url(generate_presigned_url(passport_front.s3_key)),
                    "image_back": get_image_data_uri_from_signed_url(generate_presigned_url(passport_back.s3_key))
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
