# serializers.py
from rest_framework import serializers
from core_apps.common.models import Country, State


class CountrySerializer(serializers.ModelSerializer):
    """
    Serializer for the Country model.
    """
    class Meta:
        model = Country
        fields = ['id', 'name', 'code',]
