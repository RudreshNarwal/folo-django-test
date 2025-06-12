from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from core_apps.international_wallet.models.customer import Customer
from core_apps.international_wallet.serializers.customer import CustomerSerializer


class CustomerViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows customers to be viewed.

    It is searchable by the associated user's mobile number, email, or username.
    Usage: `/api/customers/?search={mobile_number_or_email}`
    Example: `/api/customers/?search=1234567890`
    """
    queryset = Customer.objects.select_related('user').all()
    serializer_class = CustomerSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]

    # Define fields available for filtering (e.g., /api/customers/?provider=Bridge)
    filterset_fields = ['current_status', 'provider']

    # Define fields for the search parameter.
    search_fields = ['user__mobile', 'user__email', 'user__username']
