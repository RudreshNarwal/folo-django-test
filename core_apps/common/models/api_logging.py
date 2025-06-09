from django.db import models


class APILog(models.Model):
    """
    Django model to log details of outgoing API requests and their responses.

    This model captures information such as the timestamp, endpoint, HTTP method,
    request/response headers, request/response bodies, status code, and whether
    the request was successful. It uses JSONField for storing dictionary-like
    data (headers, bodies) which is suitable for PostgreSQL. For SQLite or
    MySQL, you might need to use TextField and manually serialize/deserialize JSON.
    """
    timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text="The exact time when the API request was initiated."
    )
    endpoint = models.CharField(
        max_length=255,
        help_text="The relative or absolute URL endpoint of the API request (e.g., /v0/customers)."
    )
    method = models.CharField(
        max_length=10,
        help_text="The HTTP method used for the request (e.g., GET, POST, PUT, DELETE)."
    )
    request_headers = models.JSONField(
        default=dict,
        help_text="JSON representation of the request headers sent."
    )
    request_body = models.JSONField(
        null=True, blank=True,
        help_text="JSON representation of the request body sent. Null if no body."
    )
    response_status_code = models.IntegerField(
        null=True, blank=True,
        help_text="The HTTP status code received in the API response (e.g., 200, 400, 500)."
    )
    response_headers = models.JSONField(
        null=True, blank=True,
        help_text="JSON representation of the response headers received."
    )
    response_body = models.JSONField(
        null=True, blank=True,
        help_text="JSON representation of the response body received. Null if no body."
    )
    response_time_ms = models.FloatField(
        null=True, blank=True,
        help_text="The time taken for the API call in milliseconds."
    )
    success = models.BooleanField(
        default=False,
        help_text="True if the API call was successful (e.g., 2xx status code), False otherwise."
    )
    error_message = models.TextField(
        null=True, blank=True,
        help_text="Any error message associated with a failed API call."
    )

    class Meta:
        """
        Meta options for the APILog model.
        """
        db_table = "api_log"
        verbose_name = "API Log Entry"
        verbose_name_plural = "API Log Entries"
        ordering = ['-timestamp'] # Order by timestamp in descending order (most recent first)

    def __str__(self):
        """
        String representation of an API Log entry.
        """
        return f"{self.timestamp.isoformat()} - {self.method} {self.endpoint} - Status: {self.response_status_code}"

    def save(self, *args, **kwargs):
        """
        Override save to ensure JSONField defaults are handled if needed,
        though default=dict should handle it.
        """
        if not self.request_headers:
            self.request_headers = {}
        if not self.response_headers:
            self.response_headers = {}
        super().save(*args, **kwargs)
