import base64
import hashlib
import re
from datetime import datetime, timedelta

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from django.utils import timezone
from rest_framework.permissions import BasePermission

from core_apps.common.services.api_logging_service import APILoggingService
from django.conf import settings
import requests
import logging
import json
import uuid

# Configure logging
# This basic configuration will print logs to the console.
# In a real application, you might configure it to write to a file or a logging service.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Define a custom exception for Bridge API errors
class BridgeAPIError(Exception):
    """
    Custom exception for errors returned by the Bridge API.

    Attributes:
        message (str): A human-readable error message.
        status_code (int): The HTTP status code of the response (e.g., 400, 401).
        response_data (dict): The parsed JSON response data from the API, if available.
    """

    def __init__(self, message: str, status_code: int = None, response_data: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class BridgeAPIService:
    """
    A service class for interacting with the Bridge.xyz API.

    This class encapsulates the API calls for onboarding customers and initiating transfers
    as described in the Bridge.xyz Quick Start Guide.
    """

    def __init__(self):
        """
        Initializes the BridgeAPIService with the necessary API key.

        api_key (str): Initiate from the settings.
        base_url (str): Initiate from the settings.
        """
        self.api_logging_service = APILoggingService()
        self.api_key = settings.BRIDGE_API_KEY
        self.base_url = settings.BRIDGE_BASE_URL

        # Standard headers for all API requests
        self.headers = {
            "Api-Key": self.api_key,
            "Content-Type": "application/json",  # Most Bridge API calls expect JSON
            "Accept": "application/json"  # Always request JSON response
        }
        logger.info(f"BridgeAPIService initialized with base URL: {self.base_url}")

    def _generate_idempotency_key(self) -> str:
        """
        Generates a unique Idempotency-Key for POST requests.
        Idempotency keys prevent duplicate operations if a request is retried.

        Returns:
            str: A unique UUID string.
        """
        key = str(uuid.uuid4())
        logger.debug(f"Generated idempotency key: {key}")
        return key

    def _make_request(self, method: str, endpoint: str, data: dict = None,
                      params: dict = None, include_idempotency_key: bool = False) -> dict:
        """
        Internal helper method to make HTTP requests to the Bridge API.

        Handles common request logic, error handling, and JSON parsing.

        Args:
            method (str): The HTTP method (e.g., 'GET', 'POST', 'PUT', 'DELETE').
            endpoint (str): The specific API endpoint path (e.g., '/customers', '/transfers').
            data (dict, optional): Dictionary of JSON data to send in the request body
                                   for POST/PUT requests. Defaults to None.
            params (dict, optional): Dictionary of query parameters for GET requests. Defaults to None.
            include_idempotency_key (bool): If True, an 'Idempotency-Key' header will be added
                                            to the request. Recommended for POST operations.

        Returns:
            dict: The parsed JSON response from the API.

        Raises:
            requests.exceptions.RequestException: For network-related errors (e.g., connection issues).
            BridgeAPIError: For API-specific errors (e.g., 4xx or 5xx HTTP status codes
                            with an error payload from the API).
        """
        url = f"{self.base_url}{endpoint}"

        # Create a mutable copy of headers for this request
        request_headers = self.headers.copy()
        if include_idempotency_key:
            idempotency_key = self._generate_idempotency_key()
            request_headers["Idempotency-Key"] = idempotency_key
            logger.debug(f"Requesting with Idempotency-Key: {idempotency_key}")

        # Log the request details
        log_entry = None
        start_time = timezone.now()  # Record start time for response_time_ms

        logger.info(f"Making {method} request to {url}")
        logger.debug(f"Request Headers: {request_headers}")

        if data:
            logger.debug(f"Request Body: {json.dumps(data, indent=2)}")
        if params:
            logger.debug(f"Request Params: {params}")

        try:
            # Log the request before making it
            log_entry = self.api_logging_service.create_log_entry(
                endpoint=url,
                method=method,
                request_headers=request_headers,
                request_body=data
            )

            response = requests.request(
                method,
                url,
                headers=request_headers,
                params=params,
                json=data  # 'json' parameter automatically sets Content-Type to application/json
            )
            response.raise_for_status()  # Raises HTTPError for bad responses (4xx or 5xx)

            # Return JSON response if available, otherwise an empty dict
            response_json = response.json() if response.content else {}

            end_time = timezone.now() # Record end time for response_time_ms
            response_time_ms = (end_time - start_time).total_seconds() * 1000

            # Log successful response
            if log_entry:
                self.api_logging_service.update_log_entry(
                    log_entry=log_entry,
                    response_status_code=response.status_code,
                    response_headers=dict(response.headers),
                    response_body=response_json,
                    response_time_ms=response_time_ms,
                    success=True
                )

            logger.info(f"Request to {url} successful. Status: {response.status_code}")
            logger.debug(f"Response Body: {json.dumps(response_json, indent=2)}")

            return response_json

        except requests.exceptions.HTTPError as e:
            end_time = timezone.now()
            response_time_ms = (end_time - start_time).total_seconds() * 1000
            # Attempt to parse API-specific error message from the response body
            error_message = f"API Error: {e.response.status_code}"
            error_data = None
            try:
                error_data = e.response.json()
                if "error" in error_data and "message" in error_data["error"]:
                    error_message += f" - {error_data['error']['message']}"
                elif "message" in error_data:  # Sometimes the message is directly in the root
                    error_message += f" - {error_data['message']}"
                logger.error(
                    f"HTTP Error {e.response.status_code} for {url}: {error_message}. Response: {json.dumps(error_data, indent=2)}")
            except json.JSONDecodeError:
                # If response is not JSON, use raw text
                error_message += f" - {e.response.text}"
                logger.error(
                    f"HTTP Error {e.response.status_code} for {url}: {error_message}. Raw Response: {e.response.text}")

            # Log failed HTTP response
            if log_entry:
                self.api_logging_service.update_log_entry(
                    log_entry=log_entry,
                    response_status_code=e.response.status_code,
                    response_headers=dict(e.response.headers),
                    response_body=error_data or {},  # Store error data if it's JSON
                    response_time_ms=response_time_ms,
                    success=False,
                    error_message=f"HTTP Error {e.response.status_code}: {error_message}"
                )

            raise BridgeAPIError(
                message=error_message,
                status_code=e.response.status_code,
                response_data=error_data or {"raw_response": e.response.text}
            ) from e
        except requests.exceptions.ConnectionError as e:
            end_time = timezone.now()
            response_time_ms = (end_time - start_time).total_seconds() * 1000
            # Log general request exceptions (connection, timeout)
            if log_entry:
                self.api_logging_service.update_log_entry(
                    log_entry=log_entry,
                    response_status_code=e.response.status_code,
                    response_headers={},
                    response_body=None,
                    response_time_ms=response_time_ms,
                    success=False,
                    error_message=f"Network or connection error: {e}"
                )
            logger.error(f"Network connection error to {url}: {e}")
            raise requests.exceptions.RequestException(f"Network connection error: {e}") from e
        except requests.exceptions.Timeout as e:
            end_time = timezone.now()
            response_time_ms = (end_time - start_time).total_seconds() * 1000
            # Log general request exceptions (connection, timeout)
            if log_entry:
                self.api_logging_service.update_log_entry(
                    log_entry=log_entry,
                    response_status_code=e.response.status_code,
                    response_headers={},
                    response_body=None,
                    response_time_ms=response_time_ms,
                    success=False,
                    error_message=f"Network or connection error: {e}"
                )
            logger.error(f"Request to {url} timed out: {e}")
            raise requests.exceptions.RequestException(f"Request timed out: {e}") from e
        except requests.exceptions.RequestException as e:
            end_time = timezone.now()
            response_time_ms = (end_time - start_time).total_seconds() * 1000
            # Log general request exceptions (connection, timeout)
            if log_entry:
                self.api_logging_service.update_log_entry(
                    log_entry=log_entry,
                    response_status_code=None,  # No HTTP status code for network errors
                    response_headers={},
                    response_body=None,
                    response_time_ms=response_time_ms,
                    success=False,
                    error_message=f"Network or connection error: {e}"
                )
            logger.error(f"An unexpected request error occurred for {url}: {e}")
            # Catch any other requests-related exceptions
            raise requests.exceptions.RequestException(f"An unexpected request error occurred: {e}") from e

    def request_terms_of_service_link(self) -> dict:
        """
        Requests a terms of service link for a new customer.

        Customers need to agree to Bridge's terms of services before KYC/B information
        can be processed. This endpoint returns a URL that you can use to guide the
        customer towards TOS acceptance.

        Returns:
            dict: A dictionary containing the URL for terms of service acceptance,
                  e.g., `{"url": "https://bridge.xyz/tos?..."}`.

        Raises:
            BridgeAPIError: If the API call fails (e.g., invalid API key).
            requests.exceptions.RequestException: For network-related issues.
        """
        logger.info("Attempting to request Terms of Service link.")
        try:
            response = self._make_request(
                method="POST",
                endpoint="/v0/customers/tos_links",
                params={},
                include_idempotency_key=True  # POST requests should always have idempotency keys
            )
            logger.info("Successfully requested Terms of Service link.")
            return response
        except (BridgeAPIError, requests.exceptions.RequestException) as e:
            logger.error(f"Failed to request Terms of Service link: {e}")
            raise

    def create_customer(self, customer_data: dict) -> dict:
        """
        Creates a new customer object in the Bridge system.

        This endpoint initiates the KYC (Know Your Customer) process for the user.
        The `signed_agreement_id` obtained from `request_terms_of_service_link`
        must be included in `customer_data`.

        Args:
            customer_data (dict): A dictionary containing the customer's details.
                                  Example structure:
                                  {
                                      "type": "individual", # "individual" or "business"
                                      "first_name": "John",
                                      "last_name": "Doe",
                                      "email": "email@example.com",
                                      "residential_address": {
                                          "street_line_1": "123 Main St",
                                          "city": "New York City",
                                          "subdivision": "New York",
                                          "postal_code": "10001",
                                          "country": "USA"
                                      },
                                      "birth_date": "YYYY-MM-DD",
                                      "signed_agreement_id": "<signed_agreement_id_from_tos_link>",
                                      "identifying_information": [
                                          {"type": "ssn", "issuing_country": "usa", "number": "xxx-xx-xxxx"},
                                          # Optional: drivers_license, passport etc.
                                          # {"type": "drivers_license", "issuing_country": "usa",
                                          #  "number": "XXXXXXXXXXXXX", "image_front": "data:image/jpg;base64,...",
                                          #  "image_back": "data:image/jpg;base64,..."}
                                      ]
                                  }

        Returns:
            dict: A dictionary containing the newly created customer's details, including their KYC status.

        Raises:
            BridgeAPIError: If the API call fails (e.g., invalid customer data, missing agreement ID).
            requests.exceptions.RequestException: For network-related issues.
        """
        logger.info("Attempting to create a new customer.")
        try:
            response = self._make_request(
                method="POST",
                endpoint="/v0/customers",
                data=customer_data,
                include_idempotency_key=True
            )
            logger.info("Customer created successfully.")
            return response
        except (BridgeAPIError, requests.exceptions.RequestException) as e:
            logger.error(f"Failed to create customer: {e}")
            raise


    def external_account(self, external_account_data: dict) -> dict:
        """
        Attempts to add an external account by making a request to the specified endpoint. The method
        uses the provided external account data to perform the operation.

        Args:
            external_account_data (dict): A dictionary containing the data required to add an external
            account. This dictionary must include a 'customer_id' key to indicate the associated
            customer.

        Returns:
            dict: The response returned by the request made to the external API.

        Raises:
            BridgeAPIError: If there is an API-specific error when making the request.
            requests.exceptions.RequestException: If there is a general request issue, such as a
            connectivity problem.
        """
        logger.info("Attempting to add an external account.")
        try:
            response = self._make_request(
                method="POST",
                endpoint=f"/v0/customers/{external_account_data.pop('customer_id')}/external_accounts",
                data=external_account_data,
                include_idempotency_key=True
            )
            logger.info("External account added successfully.")
            return response
        except (BridgeAPIError, requests.exceptions.RequestException) as e:
            logger.error(f"Failed to add external account: {e}")
            raise


    def initiate_transfer(self, transfer_data: dict) -> dict:
        """
        Initiates a money movement transfer (e.g., crypto to fiat, fiat to crypto).

        This endpoint facilitates moving funds based on the provided source, destination,
        amount, and payment rails.

        Args:
            transfer_data (dict): A dictionary containing the transfer details.
                                  Example structure for off-ramping USDC to fiat wire:
                                  {
                                      "amount": "100.00",        # string: Amount as a string (important for decimals)
                                      "on_behalf_of": "customer_123", # string: The ID of the customer
                                      "source": {},              # dict: Source details (can be empty if implied by from_address)
                                      "payment_rail": "polygon", # string: e.g., "polygon", "ethereum", "wire"
                                      "currency": "usdc",        # string: Currency of the source asset, e.g., "usdc", "usd"
                                      "from_address": "0xdeadbeef", # string: Source crypto address for crypto-to-fiat
                                      "destination": {           # dict: Details of the destination
                                          "payment_rail": "wire", # string: e.g., "wire", "ach"
                                          "currency": "usd",      # string: Currency of the destination, e.g., "usd"
                                          "external_account_id": "external_account_123" # string: Registered bank account ID
                                      }
                                  }

        Returns:
            dict: A dictionary containing the details of the initiated transfer.

        Raises:
            BridgeAPIError: If the API call fails (e.g., insufficient funds, invalid destination).
            requests.exceptions.RequestException: For network-related issues.
        """
        logger.info("Attempting to initiate a transfer.")
        try:
            response = self._make_request(
                method="POST",
                endpoint="/v0/transfers",
                data=transfer_data,
                include_idempotency_key=True
            )
            logger.info("Transfer initiated successfully.")
            return response
        except (BridgeAPIError, requests.exceptions.RequestException) as e:
            logger.error(f"Failed to initiate transfer: {e}")
            raise


# --- Helper Function for Verification ---
# This function can be reused easily.
def verify_signature(timestamp: str, body_data: bytes, signature: str) -> bool:
    """
    Verifies the webhook signature using the public key.

    Args:
        timestamp: The timestamp string from the 't' part of the header.
        body_data: The raw request body as bytes.
        signature: The base64-encoded signature from the 'v0' part of the header.

    Returns:
        True if the signature is valid, False otherwise.
    """
    if not all([timestamp, body_data, signature]):
        return False

    data_to_verify = f"{timestamp}.".encode('utf-8') + body_data
    digest = hashlib.sha256(data_to_verify).digest()

    try:
        webhook_public_key = settings.WEBHOOK_PUBLIC_KEY

        if not webhook_public_key:
            return False

        formatted_pem = webhook_public_key.replace('\\n', '\n')
        if not formatted_pem.startswith('-----BEGIN PUBLIC KEY-----'):
            formatted_pem = f"-----BEGIN PUBLIC KEY-----\n{formatted_pem}\n-----END PUBLIC KEY-----"

        public_key = load_pem_public_key(formatted_pem.encode())
        decoded_signature = base64.b64decode(signature)
        public_key.verify(
            decoded_signature,
            digest,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return True
    except (InvalidSignature, TypeError, ValueError) as e:
        print(f"Signature verification failed: {str(e)}")  # For debugging
        return False


class HasValidWebhookSignature(BasePermission):
    """
    DRF Permission to validate the webhook signature before the view is called.
    """
    message = "Invalid webhook signature."

    def has_permission(self, request, view):
        # 1. Get header
        signature_header = request.headers.get("X-Webhook-Signature")
        if not signature_header:
            self.message = "Malformed signature header: Header not found."
            return False

        # 2. Parse header
        match = re.match(r"^t=(\d+),v0=(.*)$", signature_header)
        if not match:
            self.message = "Malformed signature header: Does not match expected format."
            return False

        timestamp, signature = match.groups()
        if not timestamp or not signature:
            self.message = "Malformed signature header: Missing timestamp or signature."
            return False

        # 3. Check timestamp
        try:
            event_time = datetime.fromtimestamp(int(timestamp) / 1000)
            if event_time < datetime.now() - timedelta(minutes=10):
                self.message = "Invalid signature: Timestamp is too old."
                return False
        except (ValueError, OSError):
            self.message = "Invalid timestamp format."
            return False

        # 4. Verify signature
        if not verify_signature(timestamp, json.dumps(request.data, separators=(',', ':')).encode('utf-8'), signature):
            self.message = "Invalid signature!"
            return False

        return True
