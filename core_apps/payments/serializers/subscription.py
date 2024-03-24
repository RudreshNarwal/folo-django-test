from rest_framework import serializers
from core_apps.payments.models import Subscription


class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = '__all__'  # Adjust the fields based on what information you want to expose
