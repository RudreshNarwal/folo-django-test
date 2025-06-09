import requests
from django.conf import settings
from requests.exceptions import RequestException, HTTPError, ConnectionError, Timeout
from twilio.rest import Client


class VerificationCodeError(Exception):
    """Base class for exceptions related to sending verification codes."""
    pass


class GatewayRejectionError(VerificationCodeError):
    """Exception raised when a message is rejected by the gateway."""
    def __init__(self, message="Message rejected by the gateway in send_verification_code", recipients=None, mobile=None):
        self.message = message
        self.recipients = recipients
        self.mobile = mobile
        super().__init__(self.message)


def send_verification_code(mobile, code):
    message = f"Your Folo verification code is: {code}"

    if mobile.startswith('254'):
        data = {
            "username": "folomoney",
            "to": mobile,
            "message": message,
            "from": "FOLO",
        }
        headers = {
            "apiKey": settings.AFRICA_TALKING_API_KEY,
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        try:
            response = requests.post(
                f"{settings.AFRICA_TALKING_BASE_URL}/version1/messaging", headers=headers, data=data
            )
            response.raise_for_status()  # Check if the HTTP response was successful
            response_data = response.json()  # Parse the JSON response

            # Check for application-level errors in the response data
            recipients = response_data.get("SMSMessageData", {}).get("Recipients", [])
            if any((recipient.get("statusCode") == 502 or recipient.get("statusCode") == 403) for recipient in
                   recipients):
                # Handle the specific error (e.g., RejectedByGateway with statusCode 502)
                raise GatewayRejectionError(recipients=recipients, mobile=mobile)
            return response_data  # Return the successful response data

        except ValueError:
            raise VerificationCodeError("Failed to parse response as JSON")
        except (RequestException, HTTPError, ConnectionError, Timeout) as e:
            raise VerificationCodeError(f"Failed to send verification code due to a network or HTTP error: {e}")
    else:
        client = Client(settings.TWILIO_SID, settings.TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            to=mobile,
            from_="+15017250604",
            body=message
        )
