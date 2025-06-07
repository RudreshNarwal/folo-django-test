from django.db import transaction
import logging
from core_apps.common.models import APILog


# Get an instance of a logger (can be the same as in BridgeAPIService or a specific one)
logger = logging.getLogger(__name__)


class APILoggingService:
    """
    Service class for logging API requests and responses to the Django database.

    This service provides methods to create a log entry for an outgoing API request
    and then update that entry with the corresponding response details, including
    status, success, and any errors.
    """

    def __init__(self):
        """
        Initializes the APILoggingService.
        No specific configuration needed as it directly interacts with Django models.
        """
        logger.debug("APILoggingService initialized.")

    def create_log_entry(self, endpoint: str, method: str, request_headers: dict,
                         request_body: dict = None) -> APILog:
        """
        Creates a new API log entry in the database for an outgoing request.

        This method should be called *before* sending the actual HTTP request.
        The returned APILog object can then be updated with response details.

        Args:
            endpoint (str): The API endpoint being called.
            method (str): The HTTP method (e.g., 'POST', 'GET').
            request_headers (dict): A dictionary of headers sent with the request.
            request_body (dict, optional): The request body, if any. Defaults to None.

        Returns:
            APILog: The newly created APILog instance.

        Raises:
            Exception: If there's an issue saving the log entry to the database.
        """
        try:
            # Ensure request_body is stored as JSON or None
            log_entry = APILog.objects.create(
                endpoint=endpoint,
                method=method,
                request_headers=request_headers,
                request_body=request_body # JSONField handles dict directly
            )
            logger.info(f"Created API log entry for {method} {endpoint}. Log ID: {log_entry.id}")
            return log_entry
        except Exception as e:
            logger.error(f"Failed to create API log entry for {method} {endpoint}: {e}")
            # Re-raise the exception to inform the caller, or handle gracefully depending on requirements
            raise

    def update_log_entry(self, log_entry: APILog, response_status_code: int,
                         response_headers: dict, response_body: dict = None,
                         response_time_ms: float = None, success: bool = False,
                         error_message: str = None):
        """
        Updates an existing API log entry with response details.

        This method should be called *after* receiving the HTTP response.

        Args:
            log_entry (APILog): The APILog instance previously created by `create_log_entry`.
            response_status_code (int): The HTTP status code of the response.
            response_headers (dict): A dictionary of headers received in the response.
            response_body (dict, optional): The response body, if any. Defaults to None.
            response_time_ms (float, optional): The time taken for the request in milliseconds.
                                               Defaults to None.
            success (bool): True if the API call was considered successful (e.g., 2xx status code).
                            Defaults to False.
            error_message (str, optional): A descriptive error message if the call failed.
                                           Defaults to None.

        Raises:
            Exception: If there's an issue updating the log entry in the database.
        """
        try:
            with transaction.atomic(): # Use a transaction to ensure atomicity of update
                log_entry.response_status_code = response_status_code
                log_entry.response_headers = response_headers
                log_entry.response_body = response_body # JSONField handles dict directly
                log_entry.response_time_ms = response_time_ms
                log_entry.success = success
                log_entry.error_message = error_message
                log_entry.save()
            logger.info(f"Updated API log entry {log_entry.id} with status {response_status_code}. Success: {success}")
        except Exception as e:
            logger.error(f"Failed to update API log entry {log_entry.id}: {e}")
            # Re-raise or handle as per application's error strategy
            raise
