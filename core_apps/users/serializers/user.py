from rest_framework import serializers

from core_apps.users.models import User
from django_countries.serializer_fields import CountryField
from phonenumber_field.serializerfields import PhoneNumberField
from rest_framework import serializers
from django_countries.serializer_fields import CountryField
from ..models.user import User, Document, Address
from ..utils import upload_to_s3, generate_presigned_url
import base64
from django.core.files.base import ContentFile


class DocumentSerializer(serializers.ModelSerializer):
    base64_encoded_document = serializers.CharField(write_only=True, required=True)
    signed_s3_url = serializers.SerializerMethodField(read_only=True)
    media_type = serializers.CharField(read_only=True)  # Make media_type read-only

    class Meta:
        model = Document
        fields = ['id', 'document_type', 'media_type', 'signed_s3_url', 'base64_encoded_document']

    def get_signed_s3_url(self, obj):
        """
        Generate a presigned URL for accessing the uploaded document.
        """
        return generate_presigned_url(obj.s3_key)

    def validate_base64_encoded_document(self, value):
        """
        Validate that the base64_encoded_document is properly formatted and does not exceed the size limit.
        """
        try:
            # Split the base64 string to extract the media type and the actual data
            format, imgstr = value.split(';base64,')
            decoded_file = base64.b64decode(imgstr)
        except (ValueError, AttributeError, base64.binascii.Error):
            raise serializers.ValidationError("Invalid base64 encoded document.")

        # Check the file size (limit to 5MB)
        if len(decoded_file) > 5 * 1024 * 1024:  # 5MB limit
            raise serializers.ValidationError("File size exceeds the limit of 5MB.")

        # Validate the media_type
        media_type = format.split(':')[1] if ':' in format else 'application/octet-stream'
        allowed_types = ['image/jpeg', 'image/png','image/heif','image/heic', 'image/webp']
        if media_type not in allowed_types:
            raise serializers.ValidationError("Unsupported file type.")

        return value

    def create(self, validated_data):
        """
        Handle the creation of a Document instance, including decoding the base64 document,
        uploading to S3, and saving the instance to the database.
        """
        base64_encoded_document = validated_data.pop('base64_encoded_document')
        user = self.context['request'].user

        # Decode the base64 content
        try:
            format, imgstr = base64_encoded_document.split(';base64,')
            media_type = format.split(':')[1] if ':' in format else 'application/octet-stream'
            ext = format.split('/')[-1]
            decoded_file = base64.b64decode(imgstr)
        except (ValueError, AttributeError, base64.binascii.Error):
            raise serializers.ValidationError("Invalid base64 encoded document")

        # Create a ContentFile for the decoded document
        file_name = f"{validated_data['document_type']}.{ext}"
        content_file = ContentFile(decoded_file, name=file_name)

        # Upload the ContentFile to S3 with media_type as content_type
        s3_key = upload_to_s3(content_file, user.id, validated_data['document_type'], media_type)
        
        # Update or create the Document instance
        document, created = Document.objects.update_or_create(
            user=user,
            document_type=validated_data['document_type'],
            defaults={
                's3_key': s3_key,
                'media_type': media_type,
            }
        )
        return document


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = [
            'address_type', 'city', 'country',
            'line1', 'line2', 'state', 'code'
        ]


class UserSerializer(serializers.ModelSerializer):
    mobile = serializers.CharField(required=True, max_length=15, min_length=5)
    country_code = serializers.CharField(max_length=5, allow_blank=True, allow_null=True, required=False)
    nation_id = serializers.CharField(required=True, max_length=20)
    first_name = serializers.CharField(required=True, max_length=128)
    middle_name = serializers.CharField(required=False, max_length=128, allow_null=True, allow_blank=True)
    last_name = serializers.CharField(required=False, max_length=128, allow_null=True, allow_blank=True)
    email = serializers.EmailField(required=True)
    dob = serializers.DateField(required=True)
    documents = DocumentSerializer(many=True, read_only=True)
    address = AddressSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            "pkid", "id", "first_name", "middle_name", "last_name", "dob", "mobile", 'is_mobile_verified', "email",
            "gender", "nation_id", "is_email_verified", "country_code", "marital_status", "country", "city", "title",
            "documents", "address", "district_of_birth", "bridge_signed_agreement_id"
        ]

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

    def to_representation(self, instance):
        """
        Customize the representation to include documents and address.
        """
        representation = super().to_representation(instance)
        representation['documents'] = DocumentSerializer(instance.documents.all(), many=True, context=self.context).data
        representation['address'] = AddressSerializer(instance.address, context=self.context).data if hasattr(instance, 'address') else None
        return representation
