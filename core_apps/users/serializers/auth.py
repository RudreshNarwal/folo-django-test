from rest_framework import serializers


class VerifyOTPRequestSerializer(serializers.Serializer):
    otp = serializers.CharField(required=False, max_length=6, min_length=6)
    mobile = serializers.CharField(required=True, max_length=15, min_length=6)