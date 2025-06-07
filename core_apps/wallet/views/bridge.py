# bridge_integration/views.py
from django.http import JsonResponse
from django.conf import settings
import logging

# DRF imports
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

# Import the services and serializers
from core_apps.wallet.services.bridge_services import BridgeAPIService, BridgeAPIError
from core_apps.common.services.api_logging_service import APILoggingService
from core_apps.wallet.serializers import (
    CreateCustomerSerializer,
    InitiateTransferSerializer
)
import requests # Import requests directly for generic RequestException handling

logger = logging.getLogger(__name__)

# Initialize the API Logging Service once
api_logging_service = APILoggingService()
# Initialize the Bridge API service
bridge_service = BridgeAPIService()


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
        if not bridge_service:
            return Response({"error": {"message": "API Service not initialized.", "code": 500}}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            response_data = bridge_service.request_terms_of_service_link()
            # Save the signed agreement ID to the user model for future reference
            request.user.signed_agreement_id = response_data.get("signed_agreement_id")
            request.user.save(update_fields=["signed_agreement_id"])

            return Response(response_data, status=status.HTTP_200_OK)
        except BridgeAPIError as e:
            logger.error(f"Error requesting TOS link from Bridge API: {e.message}", exc_info=True)
            return Response(
                {"error": {"message": e.message, "code": e.status_code, "details": e.response_data}},
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
        if not bridge_service:
            return Response({"error": {"message": "API Service not initialized.", "code": 500}}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        serializer = CreateCustomerSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(f"Invalid request data for customer creation: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        customer_data = serializer.validated_data

        try:
            response_data = bridge_service.create_customer(customer_data)
            return Response(response_data, status=status.HTTP_200_OK) # Bridge API usually returns 200 OK
        except BridgeAPIError as e:
            logger.error(f"Error creating customer via Bridge API: {e.message}", exc_info=True)
            return Response(
                {"error": {"message": e.message, "code": e.status_code, "details": e.response_data}},
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
        if not bridge_service:
            return Response({"error": {"message": "API Service not initialized.", "code": 500}}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        serializer = InitiateTransferSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(f"Invalid request data for transfer initiation: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        transfer_data = serializer.validated_data

        try:
            response_data = bridge_service.initiate_transfer(transfer_data)
            return Response(response_data, status=status.HTTP_200_OK) # Bridge API usually returns 200 OK
        except BridgeAPIError as e:
            logger.error(f"Error initiating transfer via Bridge API: {e.message}", exc_info=True)
            return Response(
                {"error": {"message": e.message, "code": e.status_code, "details": e.response_data}},
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
