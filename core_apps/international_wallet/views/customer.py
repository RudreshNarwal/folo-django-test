from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from core_apps.international_wallet.models.customer import Customer
from core_apps.international_wallet.serializers.customer import CustomerSerializer


class CustomerViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows customers to be viewed.

    It is searchable by the associated user's mobile number, email, or username.
    Usage: `/international-customer/?search={mobile_number_or_email}`
    Example: `/international-customer/?search=1234567890`
    """
    serializer_class = CustomerSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]

    # Define fields available for filtering (e.g., /international-customer/?provider=Bridge)
    filterset_fields = ['current_status', 'provider']

    # Define fields for the search parameter.
    search_fields = ['user__mobile', 'user__email', 'user__username']

    model = Customer

    def get_queryset(self):
        return self.model.objects.select_related(
            'user',
        ).filter(
            user__is_active=True,  # Only include active users
            user_id=self.request.user.pkid
        ).order_by(
            '-created_on'
        )
