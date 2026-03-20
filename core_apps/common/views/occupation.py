# views.py
from rest_framework import generics
from rest_framework.filters import SearchFilter
from core_apps.common.models import Occupation
from core_apps.common.serializers import OccupationSerializer


class OccupationListView(generics.ListAPIView):
    """
    API view to retrieve a list of occupation.
    Supports searching by 'name' and 'code'.
    """
    queryset = Occupation.objects.all()
    serializer_class = OccupationSerializer
    filter_backends = [SearchFilter]
    search_fields = ['name', 'code']
