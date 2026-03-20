# serializers.py
from rest_framework import serializers
from core_apps.common.models import Occupation


class OccupationSerializer(serializers.ModelSerializer):
    """
    Serializer for the Country model.
    """
    class Meta:
        model = Occupation
        fields = ['id', 'name', 'code',]
