# views.py
from rest_framework import generics
from rest_framework.filters import SearchFilter
from core_apps.common.models import State
from core_apps.common.serializers import StateSerializer


class StateListView(generics.ListAPIView):
    """
    API view to retrieve a list of states.
    Filters states based on the 'country' query parameter.
    Supports searching by state 'name' and 'code'.
    """
    serializer_class = StateSerializer
    filter_backends = [SearchFilter]
    search_fields = ['name', 'code']

    def get_queryset(self):
        """
        Optionally restricts the returned states to a given country,
        by filtering against a `country` query parameter in the URL.
        """
        queryset = State.objects.all()
        country_id = self.request.query_params.get('country_id', None)
        if country_id is not None:
            queryset = queryset.filter(country__id=country_id)
        return queryset
