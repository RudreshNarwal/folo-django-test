from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from core_apps.international_wallet.models.internationl_wallet import InternationalWalletTransaction
from core_apps.international_wallet.serializers.international_wallet import InternationalWalletTransactionSerializer
from generics.utils.pagination import StandardResultSetPagination


class InternationalWalletTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows International Wallet Transaction to be viewed.

    It is searchable by the associated user's mobile number, email, or username.
    Usage: `/international-wallet-transaction/?search={mobile_number_or_email}`
    Example: `/international-wallet-transaction/?search=1234567890`
    """
    pagination_class = StandardResultSetPagination
    serializer_class = InternationalWalletTransactionSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]

    # Define fields available for filtering (e.g., /international-wallet-transaction/?provider=Bridge)
    filterset_fields = ['user_id', 'customer_id']

    # Define fields for the search parameter.
    search_fields = ['user__mobile', 'user__email', 'user__username']

    model = InternationalWalletTransaction

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
