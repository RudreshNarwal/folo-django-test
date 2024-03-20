from rest_framework import serializers


class VerifyOTPRequestSerializer(serializers.Serializer):
    otp = serializers.CharField(required=False, max_length=6, min_length=6)
    mobile = serializers.CharField(required=True, max_length=15, min_length=6)
    
    def validate_mobile(self, value):
        # Default country code
        default_country_code = '+254'
        # Possible country code prefixes
        country_code_prefixes = ['+254', '+91', '+1', '+234', '+27', '+20']  # Add more as needed
        
        # Initialize variables
        country_code = default_country_code
        mobile_number = value
        
        # Detect and extract the country code if present
        for prefix in country_code_prefixes:
            if value.startswith(prefix):
                country_code = prefix
                mobile_number = value[len(prefix):]
                break
        # Update the internal representation with separated country code and mobile number
        self.initial_data.update({
            'country_code': country_code,
            'mobile': mobile_number
        })
        
        return mobile_number