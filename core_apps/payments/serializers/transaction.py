from rest_framework import serializers
from ..models import Transaction

class TransactionCreateSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)

    class Meta:
        model = Transaction
        fields = ['plan', 'payment_method', 'amount']
        extra_kwargs = {
            'plan': {'required': True, 'write_only': True},
            'payment_method': {'required': True, 'write_only': True},
        }

class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = '__all__'