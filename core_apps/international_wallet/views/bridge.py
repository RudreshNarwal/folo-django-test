from django.http import JsonResponse
import logging
from urllib.parse import urlparse, parse_qs

# DRF imports
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from core_apps.international_wallet.models import Customer
# Import the services and serializers
from core_apps.international_wallet.services.bridge import BridgeAPIService, BridgeAPIError
from core_apps.international_wallet.serializers import (
    CreateCustomerSerializer,
    InitiateTransferSerializer, CustomerSerializer
)
import requests # Import requests directly for generic RequestException handling

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


class InitiateTransferAPI(APIView):
    """
    API endpoint to initiate a money transfer through the Bridge API.

    - Requires authentication (IsAuthenticated).
    - Expects a JSON POST request with transfer details.
    - Returns a JSON response with the transfer details or an error.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        """
        Handles POST requests to initiate a transfer.
        """
        serializer = InitiateTransferSerializer(data=request.data, context={"request": self.request})
        if not serializer.is_valid():
            logger.warning(f"Invalid request data for transfer initiation: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        transfer_data = serializer.validated_data

        try:
            # Initialize the Bridge API service
            bridge_service = BridgeAPIService()
            if not bridge_service:
                return Response({"error": {"message": "API Service not initialized.", "code": 500}},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            response_data = bridge_service.initiate_transfer(transfer_data)
            return Response(response_data, status=status.HTTP_200_OK) # Bridge API usually returns 200 OK
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
