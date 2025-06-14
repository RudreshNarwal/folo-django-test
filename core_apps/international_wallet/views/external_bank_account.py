from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from core_apps.international_wallet.models.external_bank_account import ExternalBankAccount
from core_apps.international_wallet.serializers.external_bank_account import ExternalBankAccountSerializer


class ExternalBankAccountViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows External Bank Account to be viewed.

    It is searchable by the associated user's mobile number, email, or username.
    Usage: `/international-customer-external-account/?search={mobile_number_or_email}`
    Example: `/international-customer-external-account/?search=1234567890`
    """
    serializer_class = ExternalBankAccountSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]

    # Define fields available for filtering (e.g., /international-customer-external-account/?provider=Bridge)
    filterset_fields = ['user_id', 'customer_id']

    # Define fields for the search parameter.
    search_fields = ['user__mobile', 'user__email', 'user__username']

    model = ExternalBankAccount

    def get_queryset(self):
        return self.model.objects.select_related(
            'user', 'customer'
        ).filter(
            user__is_active=True,  # Only include active users
            customer__is_active=True,  # Only include active customers
            user_id=self.request.user.pkid
        ).order_by(
            '-created_on'
        )
