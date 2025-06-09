# serializers.py
from rest_framework import serializers
from core_apps.common.models import State
from core_apps.common.serializers.country import CountrySerializer


class StateSerializer(serializers.ModelSerializer):
    """
    Serializer for the State model.
    """
    country = CountrySerializer(read_only=True)

    class Meta:
        model = State
        fields = ['id', 'name', 'code', 'country']
