from rest_framework import serializers

from core_apps.transunion.models import CreditReport


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128)
    code = serializers.CharField(max_length=10)
    infinityCode = serializers.CharField(max_length=15, source='infinity_code')
    reportReason = serializers.IntegerField(source='report_reason')
    reportSector = serializers.IntegerField(source='report_sector')
    names = serializers.CharField(max_length=255)
    documentNumber = serializers.CharField(max_length=50, source='document_number')
    telephoneMobile = serializers.CharField(max_length=15, source='telephone_mobile')

    def create(self, validated_data):
        # This method would be where you integrate the logic to create a new user, report, etc., based on the validated data
        # For instance, creating a `User` instance. This is just a placeholder.
        #TODO fix this
        cr = CreditReport.objects.create(**validated_data)
        return cr

    def update(self, instance, validated_data):
        # Implement the update logic if necessary for your application
        instance.username = validated_data.get('username', instance.username)
        # Update other fields similarly...
        instance.save()
        return instance
