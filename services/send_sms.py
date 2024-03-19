import requests
from requests.exceptions import RequestException, HTTPError, ConnectionError, Timeout

class VerificationCodeError(Exception):
    """Base class for exceptions related to sending verification codes."""
    pass

class GatewayRejectionError(VerificationCodeError):
    """Exception raised when a message is rejected by the gateway."""
    def __init__(self, message="Message rejected by the gateway in send_verification_code", recipients=None):
        self.message = message
        self.recipients = recipients
        super().__init__(self.message)

def send_verification_code(mobile, code):
    api_url = "https://api.africastalking.com/version1/messaging"
    api_key = "dfb804d5dfe09d5d1f4bd5da2be97ed3e8d1e357fd64c54a40e918d253c66d92"
    username = "folomoney"
    sender_id = "FOLO"
    message = f"Your Folo verification code is: {code}"

    headers = {
        "apiKey": api_key,
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    
    mobile_numbers=f"+254{mobile}"

    data = {
        "username": username,
        "to": mobile_numbers,
        "message": message,
        "from": sender_id,
    }
    
    try:
        response = requests.post(api_url, headers=headers, data=data)
        response.raise_for_status()  # Check if the HTTP response was successful
        response_data = response.json()  # Parse the JSON response
        
        # Check for application-level errors in the response data
        recipients = response_data.get("SMSMessageData", {}).get("Recipients", [])
        if any((recipient.get("statusCode") == 502 or recipient.get("statusCode") == 403) for recipient in recipients):
            # Handle the specific error (e.g., RejectedByGateway with statusCode 502)
            raise GatewayRejectionError(recipients=recipients)
        return response_data  # Return the successful response data
    
    except ValueError:
        raise VerificationCodeError("Failed to parse response as JSON")
    except (RequestException, HTTPError, ConnectionError, Timeout) as e:
        raise VerificationCodeError(f"Failed to send verification code due to a network or HTTP error: {e}")
