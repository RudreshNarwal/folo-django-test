from rest_framework import serializers
from .models import Transaction

class TransactionCreateSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)

    class Meta:
        model = Transaction
        fields = ['plan_id', 'payment_method_id', 'amount']
        extra_kwargs = {
            'plan_id': {'required': True},
            'payment_method_id': {'required': True},
        }
