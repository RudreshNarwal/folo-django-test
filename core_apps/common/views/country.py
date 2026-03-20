# views.py
from rest_framework import generics
from rest_framework.filters import SearchFilter
from core_apps.common.models import Country
from core_apps.common.serializers import CountrySerializer


class CountryListView(generics.ListAPIView):
    """
    API view to retrieve a list of countries.
    Supports searching by 'name' and 'code'.
    """
    queryset = Country.objects.all()
    serializer_class = CountrySerializer
    filter_backends = [SearchFilter]
    search_fields = ['name', 'code']
