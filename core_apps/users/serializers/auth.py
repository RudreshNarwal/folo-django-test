from rest_framework import serializers
from core_apps.users.models import User


class RegisterUserMobileSerializer(serializers.ModelSerializer):
    mobile = serializers.CharField(required=True, max_length=15, min_length=5)
    country_code = serializers.CharField(max_length=5, allow_blank=True, required=False)
    
    def validate_mobile(self, value):
        # Get country code from request body first
        request_country_code = self.initial_data.get('country_code')
        
        # Default country code if none provided
        default_country_code = '+254'
        
        # Comprehensive list of country code prefixes
        country_code_prefixes = [
            '+254', '+1', '+44', '+61', '+91', '+234', '+27', '+256', '+255', '+250',
            '+251', '+233', '+221', '+225', '+226', '+223', '+227', '+235', '+237',
            '+236', '+242', '+243', '+241', '+240', '+244', '+260', '+263', '+267',
            '+264', '+266', '+268', '+258', '+265', '+261', '+230', '+248', '+269',
            '+253', '+252', '+291', '+249', '+211', '+20', '+218', '+216', '+213',
            '+212', '+222', '+231', '+232', '+224', '+245', '+238', '+220', '+228',
            '+229', '+86', '+81', '+82', '+66', '+84', '+63', '+62', '+60', '+65',
            '+880', '+92', '+94', '+977', '+975', '+95', '+855', '+856', '+976',
            '+93', '+98', '+964', '+963', '+961', '+962', '+972', '+970', '+966',
            '+967', '+968', '+971', '+974', '+973', '+965', '+90', '+357', '+995',
            '+374', '+994', '+7', '+998', '+993', '+992', '+996', '+49', '+33',
            '+39', '+34', '+351', '+31', '+32', '+352', '+41', '+43', '+45', '+46',
            '+47', '+358', '+354', '+353', '+48', '+420', '+421', '+36', '+386',
            '+385', '+387', '+381', '+382', '+389', '+355', '+30', '+359', '+40',
            '+373', '+380', '+375', '+370', '+371', '+372', '+55', '+54', '+56',
            '+51', '+57', '+58', '+593', '+591', '+595', '+598', '+592', '+597',
            '+594', '+52', '+502', '+501', '+503', '+504', '+505', '+506', '+507',
            '+53', '+509', '+64', '+679', '+675', '+677', '+678', '+687', '+689',
            '+676', '+685', '+686', '+688', '+674', '+680', '+691', '+692', '+682',
            '+683', '+690', '+681'
        ]
        
        # Initialize variables
        mobile_number = value
        country_code = None
        
        # Check if mobile number already contains a country code prefix
        for prefix in country_code_prefixes:
            if value.startswith(prefix):
                country_code = prefix
                mobile_number = value[len(prefix):]
                break
        
        # If no country code found in mobile number, use the one from request body or default
        if country_code is None:
            if request_country_code and request_country_code in country_code_prefixes:
                country_code = request_country_code
            else:
                country_code = default_country_code
        
        # Update the internal representation with separated country code and mobile number
        self.initial_data.update({
            'country_code': country_code,
            'mobile': mobile_number
        })
        
        return mobile_number
    
    class Meta:
        model = User
        fields = ["mobile", "country_code"]


class VerifyOTPRequestSerializer(serializers.Serializer):
    otp = serializers.CharField(required=False, max_length=6, min_length=6)
    mobile = serializers.CharField(required=True, max_length=15, min_length=6)
    country_code = serializers.CharField(max_length=5, allow_blank=True, required=False)
    
    def validate_mobile(self, value):
        # Get country code from request body first
        request_country_code = self.initial_data.get('country_code')
        
        # Default country code if none provided
        default_country_code = '+254'
        
        # Comprehensive list of country code prefixes
        country_code_prefixes = [
            '+254', '+1', '+44', '+61', '+91', '+234', '+27', '+256', '+255', '+250',
            '+251', '+233', '+221', '+225', '+226', '+223', '+227', '+235', '+237',
            '+236', '+242', '+243', '+241', '+240', '+244', '+260', '+263', '+267',
            '+264', '+266', '+268', '+258', '+265', '+261', '+230', '+248', '+269',
            '+253', '+252', '+291', '+249', '+211', '+20', '+218', '+216', '+213',
            '+212', '+222', '+231', '+232', '+224', '+245', '+238', '+220', '+228',
            '+229', '+86', '+81', '+82', '+66', '+84', '+63', '+62', '+60', '+65',
            '+880', '+92', '+94', '+977', '+975', '+95', '+855', '+856', '+976',
            '+93', '+98', '+964', '+963', '+961', '+962', '+972', '+970', '+966',
            '+967', '+968', '+971', '+974', '+973', '+965', '+90', '+357', '+995',
            '+374', '+994', '+7', '+998', '+993', '+992', '+996', '+49', '+33',
            '+39', '+34', '+351', '+31', '+32', '+352', '+41', '+43', '+45', '+46',
            '+47', '+358', '+354', '+353', '+48', '+420', '+421', '+36', '+386',
            '+385', '+387', '+381', '+382', '+389', '+355', '+30', '+359', '+40',
            '+373', '+380', '+375', '+370', '+371', '+372', '+55', '+54', '+56',
            '+51', '+57', '+58', '+593', '+591', '+595', '+598', '+592', '+597',
            '+594', '+52', '+502', '+501', '+503', '+504', '+505', '+506', '+507',
            '+53', '+509', '+64', '+679', '+675', '+677', '+678', '+687', '+689',
            '+676', '+685', '+686', '+688', '+674', '+680', '+691', '+692', '+682',
            '+683', '+690', '+681'
        ]
        
        # Initialize variables
        mobile_number = value
        country_code = None
        
        # Check if mobile number already contains a country code prefix
        for prefix in country_code_prefixes:
            if value.startswith(prefix):
                country_code = prefix
                mobile_number = value[len(prefix):]
                break
        
        # If no country code found in mobile number, use the one from request body or default
        if country_code is None:
            if request_country_code and request_country_code in country_code_prefixes:
                country_code = request_country_code
            else:
                country_code = default_country_code
        
        # Update the internal representation with separated country code and mobile number
        self.initial_data.update({
            'country_code': country_code,
            'mobile': mobile_number
        })
        
        return mobile_number