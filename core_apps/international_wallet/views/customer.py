import logging

import requests
from rest_framework import viewsets, filters, status
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.response import Response

from core_apps.international_wallet.models.customer import Customer
from core_apps.international_wallet.serializers.customer import CustomerSerializer, CustomerWalletDetailsSerializer
from core_apps.international_wallet.services import BridgeAPIService, BridgeAPIError
from generics.utils.pagination import StandardResultSetPagination

# Configure logging
logger = logging.getLogger(__name__)


class CustomerViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows customers to be viewed.

    It is searchable by the associated user's mobile number, email, or username.
    Usage: `/international-customer/?search={mobile_number_or_email}`
    Example: `/international-customer/?search=1234567890`
    """
    serializer_class = CustomerSerializer
    wallet_details_serializer_class = CustomerWalletDetailsSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    pagination_class = StandardResultSetPagination

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

    @action(detail=False, methods=['GET'], url_path='wallet-details')
    def wallet_details(self, request):
        """
        A custom GET endpoint for wallet details data.
        Accessible at: /international-wallet/wallet-details/
        """
        try:
            serializer = self.wallet_details_serializer_class(data=request.data, context={'request': request})
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            # Initialize the Bridge API service
            bridge_service = BridgeAPIService()
            # Fetch wallet details from the Bridge API
            wallet_details = bridge_service.wallet_details(serializer.data)
            # If no wallet details are found, return a 404 response
            if not wallet_details:
                return Response({"detail": "No wallet details found."}, status=status.HTTP_404_NOT_FOUND)

            return Response(wallet_details, status=status.HTTP_200_OK)
        except BridgeAPIError as e:
            logger.error(f"Error requesting wallet details from Bridge API: {str(e)}", exc_info=True)
            return Response(
                {"error": {"message": str(e), "code": e.status_code, "details": e.response_data}},
                status=e.status_code
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error requesting wallet details: {e}", exc_info=True)
            return Response(
                {"error": {"message": "Network or external service error.", "details": str(e)}},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except Exception as e:
            logger.error(f"Unexpected error in wallet_details: {e}", exc_info=True)
            return Response(
                {"error": {"message": "Internal Server Error.", "details": str(e)}},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['GET'], url_path='all-wallets')
    def all_wallets(self, request):
        """
        A custom GET endpoint for all wallets.
        Accessible at: /international-wallet/all-wallets/
        """
        try:
            serializer = self.wallet_details_serializer_class(data=request.data, context={'request': request})
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            # Initialize the Bridge API service
            bridge_service = BridgeAPIService()
            # Fetch all wallets from the Bridge API
            all_wallets = bridge_service.all_wallets(serializer.data)
            # If no wallet details are found, return a 404 response
            if not all_wallets:
                return Response({"detail": "No wallet details found."}, status=status.HTTP_404_NOT_FOUND)

            return Response(all_wallets, status=status.HTTP_200_OK)
        except BridgeAPIError as e:
            logger.error(f"Error requesting all wallet from Bridge API: {str(e)}", exc_info=True)
            return Response(
                {"error": {"message": str(e), "code": e.status_code, "details": e.response_data}},
                status=e.status_code
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error requesting all wallet: {e}", exc_info=True)
            return Response(
                {"error": {"message": "Network or external service error.", "details": str(e)}},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except Exception as e:
            logger.error(f"Unexpected error in all_wallets: {e}", exc_info=True)
            return Response(
                {"error": {"message": "Internal Server Error.", "details": str(e)}},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['GET'], url_path='wallets')
    def wallets(self, request):
        """
        A custom GET endpoint for wallets of an account.
        Accessible at: /international-wallet/wallets/
        """
        # Initialize the Bridge API service
        try:
            bridge_service = BridgeAPIService()
            # Fetch all account wallets from the Bridge API
            wallets = bridge_service.all_account_wallets()
            # If no wallet details are found, return a 404 response
            if not wallets:
                return Response({"detail": "No wallet details found."}, status=status.HTTP_404_NOT_FOUND)

            return Response(wallets, status=status.HTTP_200_OK)
        except BridgeAPIError as e:
            logger.error(f"Error requesting all account wallets from Bridge API: {str(e)}", exc_info=True)
            return Response(
                {"error": {"message": str(e), "code": e.status_code, "details": e.response_data}},
                status=e.status_code
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error requesting all account wallets: {e}", exc_info=True)
            return Response(
                {"error": {"message": "Network or external service error.", "details": str(e)}},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except Exception as e:
            logger.error(f"Unexpected error in wallets: {e}", exc_info=True)
            return Response(
                {"error": {"message": "Internal Server Error.", "details": str(e)}},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['GET'], url_path='wallet-balances')
    def wallet_balances(self, request):
        """
        A custom GET endpoint for wallet balances.
        Accessible at: /international-wallet/wallet-balances/
        """
        # Initialize the Bridge API service
        try:
            bridge_service = BridgeAPIService()
            # Fetch all account wallet balances from the Bridge API
            wallets = bridge_service.total_balances()
            # If no wallet balances detail found, return a 404 response
            if not wallets:
                return Response({"detail": "No wallet details found."}, status=status.HTTP_404_NOT_FOUND)

            return Response(wallets, status=status.HTTP_200_OK)
        except BridgeAPIError as e:
            logger.error(f"Error requesting all account wallet balances from Bridge API: {str(e)}", exc_info=True)
            return Response(
                {"error": {"message": str(e), "code": e.status_code, "details": e.response_data}},
                status=e.status_code
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error requesting all account wallet balances: {e}", exc_info=True)
            return Response(
                {"error": {"message": "Network or external service error.", "details": str(e)}},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except Exception as e:
            logger.error(f"Unexpected error in wallet_balances: {e}", exc_info=True)
            return Response(
                {"error": {"message": "Internal Server Error.", "details": str(e)}},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['GET'], url_path='wallet-history')
    def wallet_history(self, request):
        """
        A custom GET endpoint for wallet history.
        Accessible at: /international-wallet/wallet-history/
        """
        # Initialize the Bridge API service
        try:
            serializer = self.wallet_details_serializer_class(data=request.data, context={'request': request})
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            bridge_service = BridgeAPIService()
            # Fetch all account wallet history from the Bridge API
            wallets = bridge_service.wallet_history(serializer.data)
            # If no wallet history detail found, return a 404 response
            if not wallets:
                return Response({"detail": "No wallet history found."}, status=status.HTTP_404_NOT_FOUND)

            return Response(wallets, status=status.HTTP_200_OK)
        except BridgeAPIError as e:
            logger.error(f"Error requesting wallet history from Bridge API: {str(e)}", exc_info=True)
            return Response(
                {"error": {"message": str(e), "code": e.status_code, "details": e.response_data}},
                status=e.status_code
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error requesting wallet history: {e}", exc_info=True)
            return Response(
                {"error": {"message": "Network or external service error.", "details": str(e)}},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except Exception as e:
            logger.error(f"Unexpected error in wallet_history: {e}", exc_info=True)
            return Response(
                {"error": {"message": "Internal Server Error.", "details": str(e)}},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
