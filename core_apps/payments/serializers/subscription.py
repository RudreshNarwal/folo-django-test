from rest_framework import serializers
from core_apps.payments.models import Plan, Subscription


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = '__all__'  # Adjust this to include the fields you want to expose

class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)
    class Meta:
        model = Subscription
        fields = '__all__'  # Adjust the fields based on what information you want to expose
