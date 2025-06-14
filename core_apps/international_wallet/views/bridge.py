from django.db import transaction
from django.http import JsonResponse
import logging
from urllib.parse import urlparse, parse_qs

# DRF imports
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from core_apps.international_wallet.models import Customer, InternationalWalletTransaction
from core_apps.international_wallet.services import (
    ExternalBankAccountService, BridgeAPIService, BridgeAPIError, InternationalWalletTransactionService
)

from core_apps.international_wallet.serializers import (
    CreateCustomerSerializer, CustomerSerializer, ExternalAccountSerializer, InitiateTransferSerializer,
    InternationalWalletTransactionSerializer
)
import requests # Import requests directly for generic RequestException handling

# Configure logging
logger = logging.getLogger(__name__)


# Helper function for consistent JSON error responses (can be reused if needed outside APIView)
def _error_response(message: str, status_code_int: int, details: dict = None) -> JsonResponse:
    """
    Creates a standardized JSON error response.
    """
    response_data = {"error": {"message": message, "code": status_code_int}}
    if details:
        response_data["error"].update(details)
    return JsonResponse(response_data, status=status_code_int)


class RequestTOSLinkAPI(APIView):
    """
    API endpoint to request the Terms of Service link for a customer.

    - Requires authentication (IsAuthenticated).
    - Expects a JSON POST request with an optional 'redirect_uri'.
    - Returns a JSON response with the TOS URL or an error.
    """
    permission_classes = [IsAuthenticated]

    @transaction.atomic()
    def post(self, request, *args, **kwargs):
        """
        Handles POST requests to get a TOS link.
        """
        # Initialize the Bridge API service
        bridge_service = BridgeAPIService()

        if not bridge_service:
            return Response({"error": {"message": "API Service not initialized.", "code": 500}}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            response_data = bridge_service.request_terms_of_service_link()
            # Save the signed agreement ID to the user model for future reference
            if response_data and response_data.get("url", None):
                # Parse the URL
                parsed_url = urlparse(response_data["url"])

                # Extract the query parameters
                query_params = parse_qs(parsed_url.query)

                # Get the session_token
                signed_agreement_id = query_params.get('session_token', [None])[0]
                # Create the Customer instance with the signed agreement ID
                Customer.objects.create(
                    user=request.user,
                    provider='BRIDGE',
                    signed_agreement_id=signed_agreement_id,
                    created_by=request.user,
                )

            return Response(response_data, status=status.HTTP_200_OK)
        except BridgeAPIError as e:
            logger.error(f"Error requesting TOS link from Bridge API: {str(e)}", exc_info=True)
            return Response(
                {"error": {"message": str(e), "code": e.status_code, "details": e.response_data}},
                status=e.status_code
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error requesting TOS link: {e}", exc_info=True)
            return Response(
                {"error": {"message": "Network or external service error.", "details": str(e)}},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except Exception as e:
            logger.error(f"Unexpected error in RequestTOSLinkAPI: {e}", exc_info=True)
            return Response(
                {"error": {"message": "Internal Server Error.", "details": str(e)}},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CreateCustomerAPI(APIView):
    """
    API endpoint to create a new customer in the Bridge system.

    - Requires authentication (IsAuthenticated).
    - Expects a JSON POST request with customer details.
    - Returns a JSON response with the created customer's details or an error.
    """
    permission_classes = [IsAuthenticated]

    @transaction.atomic()
    def post(self, request, *args, **kwargs):
        """
        Handles POST requests to create a customer.
        """
        serializer = CreateCustomerSerializer(data=request.data, context={"request": self.request})
        if not serializer.is_valid():
            logger.warning(f"Invalid request data for customer creation: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        customer_data = serializer.validated_data

        try:
            # Initialize the Bridge API service
            bridge_service = BridgeAPIService()
            if not bridge_service:
                return Response({"error": {"message": "API Service not initialized.", "code": 500}},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            response_data = bridge_service.create_customer(customer_data)
            # Update a Customer instance in the database
            Customer.objects.filter(
                user=request.user,
                provider='BRIDGE'
            ).update(
                customer_id=response_data.get("id"),
                current_status=response_data.get("status").upper(),
                updated_by=request.user,
            )
            return Response(
                CustomerSerializer(Customer.objects.get(user=request.user, provider='BRIDGE')).data,
                status=status.HTTP_200_OK
            ) # Bridge API usually returns 200 OK
        except BridgeAPIError as e:
            logger.error(f"Error creating customer via Bridge API: {str(e)}", exc_info=True)
            return Response(
                {"error": {"message": str(e), "code": e.status_code, "details": e.response_data}},
                status=e.status_code
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error creating customer: {e}", exc_info=True)
            return Response(
                {"error": {"message": "Network or external service error.", "details": str(e)}},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except Exception as e:
            logger.error(f"Unexpected error in CreateCustomerAPI: {e}", exc_info=True)
            return Response(
                {"error": {"message": "Internal Server Error.", "details": str(e)}},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ExternalAccountAPI(APIView):
    """
    API endpoint to associate the external accounts through the Bridge API.

    - Requires authentication (IsAuthenticated).
    - Expects a JSON POST request with external account details.
    - Returns a JSON response with the external account details or an error.
    """
    permission_classes = [IsAuthenticated]

    @transaction.atomic()
    def post(self, request, *args, **kwargs):
        """
        Handles POST requests an external account.
        """
        serializer = ExternalAccountSerializer(data=request.data, context={"request": self.request})
        if not serializer.is_valid():
            logger.warning(f"Invalid request data for external account: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        external_account_data = serializer.validated_data

        try:
            # Initialize the Bridge API service
            bridge_service = BridgeAPIService()
            if not bridge_service:
                return Response({"error": {"message": "API Service not initialized.", "code": 500}},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            response_data = bridge_service.external_account(external_account_data)

            # Update the account instance with the external account details
            external_bank_account_service = ExternalBankAccountService()
            external_bank_account = external_bank_account_service.create_bank_account(
                user=request.user,
                data={
                    "customer_id": external_account_data.get("customer_id"),
                    "account_owner_name": external_account_data.get("account_owner_name"),
                    "bank_name": external_account_data.get("bank_name"),
                    "account_name": external_account_data.get("account_name"),
                    "account_number": external_account_data.get("account_number"),
                    "iban": external_account_data.get("iban", None),
                    "swift_bic": external_account_data.get("swift_bic", None),
                    "routing_number": external_account_data.get("routing_number"),
                    "currency": response_data.get("currency", "na").upper(),
                    "account_type": response_data.get("account_type", "Unknown").upper(),
                }
            )
            return Response(ExternalAccountSerializer(external_bank_account).data, status=status.HTTP_200_OK) # Bridge API usually returns 200 OK
        except BridgeAPIError as e:
            logger.error(f"Error external account via Bridge API: {str(e)}", exc_info=True)
            return Response(
                {"error": {"message": str(e), "code": e.status_code, "details": e.response_data}},
                status=e.status_code
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error external account: {e}", exc_info=True)
            return Response(
                {"error": {"message": "Network or external service error.", "details": str(e)}},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except Exception as e:
            logger.error(f"Unexpected error in ExternalAccountAPI: {e}", exc_info=True)
            return Response(
                {"error": {"message": "Internal Server Error.", "details": str(e)}},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class InitiateTransferAPI(APIView):
    """
    API endpoint to initiate a money transfer through the Bridge API.

    - Requires authentication (IsAuthenticated).
    - Expects a JSON POST request with transfer details.
    - Returns a JSON response with the transfer details or an error.
    """
    permission_classes = [IsAuthenticated]

    @transaction.atomic()
    def post(self, request, *args, **kwargs):
        """
        Handles POST requests to initiate a transfer.
        """
        serializer = InitiateTransferSerializer(data=request.data, context={"request": self.request})
        if not serializer.is_valid():
            logger.warning(f"Invalid request data for transfer initiation: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        transfer_data = serializer.validated_data
        # Create the InternationalWalletTransaction instance with the transfer details
        international_wallet_txn_service = InternationalWalletTransactionService()
        wallet_transaction = international_wallet_txn_service.create_transaction(
            user=request.user,
            **{
                "amount": transfer_data.get("amount"),
                "source_payment_rail": transfer_data.pop("source_payment_rail").upper(),
                "source_currency": transfer_data.pop("source_currency").upper(),
                "from_address": transfer_data.pop("from_address"),
                "destination_payment_rail": transfer_data.pop("destination_payment_rail").upper(),
                "destination_currency": transfer_data.pop("destination_currency").upper(),
                "external_account_id": transfer_data.pop("external_account_id"),
                "customer_id": transfer_data.pop("customer_id"),
            }
        )

        if not wallet_transaction:
            logger.error("Failed to create InternationalWalletTransaction.")
            return Response(
                {"error": {"message": "Failed to create transaction.", "code": 500}},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        try:
            # Initialize the Bridge API service
            bridge_service = BridgeAPIService()
            if not bridge_service:
                return Response({"error": {"message": "API Service not initialized.", "code": 500}},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            response_data = bridge_service.initiate_transfer(transfer_data)
            # Update the InternationalWalletTransaction instance with the transfer details
            international_wallet_txn_service.update_transaction(
                wallet_transaction.transaction_id,
                **{
                    "transaction_id": response_data.get("id"),
                    "client_reference_id": response_data.get("client_reference_id"),
                    "state": response_data.get("status").upper(),
                    "to_address": transfer_data.get("source_deposit_instructions", {}).get("to_address", None),
                    "receipt_url": response_data.get("receipt", {}).get("url", None),
                    "final_amount": response_data.get("receipt", {}).get("final_amount", None),
                    "developer_fee": response_data.get("receipt", {}).get("developer_fee", None),
                    "exchange_fee": response_data.get("receipt", {}).get("exchange_fee", None),
                    "gas_fee": response_data.get("receipt", {}).get("gas_fe", None),
                    "updated_by": request.user
                }
            )
            return Response(InternationalWalletTransactionSerializer(InternationalWalletTransaction.objects.get()).data, status=status.HTTP_200_OK) # Bridge API usually returns 200 OK
        except BridgeAPIError as e:
            logger.error(f"Error initiating transfer via Bridge API: {str(e)}", exc_info=True)
            return Response(
                {"error": {"message": str(e), "code": e.status_code, "details": e.response_data}},
                status=e.status_code
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error initiating transfer: {e}", exc_info=True)
            return Response(
                {"error": {"message": "Network or external service error.", "details": str(e)}},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except Exception as e:
            logger.error(f"Unexpected error in InitiateTransferAPI: {e}", exc_info=True)
            return Response(
                {"error": {"message": "Internal Server Error.", "details": str(e)}},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
