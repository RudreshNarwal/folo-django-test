import requests
import logging
import re
from django.conf import settings
from requests.exceptions import HTTPError, RequestException, Timeout

logger = logging.getLogger(__name__)


class SCAService:
    """
    Service for handling Strong Customer Authentication (SCA) operations.
    Manages JWT upgrades and SCA header parsing for DTB API interactions.
    """

    BASE_URL = 'https://api.astraafrica.co/astra-conductor/rest/v1'

    def __init__(self):
        self.session = requests.Session()
        self.headers = {'Content-Type': 'application/json'}

    def parse_sca_challenge(self, response):
        """
        Parse SCA challenge from DTB 403 response headers.

        Args:
            response: requests.Response object from DTB API call

        Returns:
            dict: SCA challenge details or None if not an SCA response
        """
        if response.status_code != 403:
            return None

        sca_header = response.headers.get('SCA')
        if not sca_header:
            return None

        # Parse header format: "SCA id=84b479c1edaa44d8b15a473614a24438;type=OTP"
        intent_id_match = re.search(r'id=([^;]+)', sca_header)
        type_match = re.search(r'type=([^;]+)', sca_header)

        if not intent_id_match:
            logger.warning(f"Could not parse intent_id from SCA header: {sca_header}")
            return None

        return {
            'requires_sca': True,
            'intent_id': intent_id_match.group(1),
            'sca_type': type_match.group(1) if type_match else 'OTP',
            'header': sca_header
        }

    def upgrade_jwt(self, intent_id, otp, current_jwt=None):
        """
        Upgrade JWT using SCA credentials.

        Args:
            intent_id (str): SCA intent ID from challenge
            otp (str): One-time password from user
            current_jwt (str, optional): Current JWT token to be upgraded

        Returns:
            dict: Upgraded JWT details

        Raises:
            SCAServiceError: If JWT upgrade fails
        """
        url = f'{self.BASE_URL}/authentication/upgrade-jwt'

        payload = {
            "intentId": intent_id,
            "otp": otp
        }

        # Prepare headers with current JWT if provided
        headers = self.headers.copy()
        if current_jwt:
            headers['Authorization'] = f'Bearer {current_jwt}'
            logger.debug(f"Upgrading JWT with Authorization header included")
        else:
            logger.warning(f"Upgrading JWT without current JWT - this may cause 404 error")

        try:
            logger.info(f"Calling upgrade-jwt endpoint: {url} with intentId: {intent_id}")
            logger.debug(f"Request headers: {headers}")
            response = self.session.post(
                url,
                json=payload,
                headers=headers,
                timeout=10,
                verify=True
            )
            response.raise_for_status()

            data = response.json()

            if 'headerValue' not in data:
                raise SCAServiceError("Invalid response from DTB auth service: missing headerValue")

            jwt_token = data['headerValue'].split(' ')[1]

            return {
                'jwt_token': jwt_token,
                'session_id': data.get('sessionId'),
                'expires_at': data.get('expiresAt')
            }

        except HTTPError as http_err:
            resp = http_err.response
            logger.error(f"JWT upgrade failed: {resp.status_code} {resp.text}")
            raise SCAServiceError(f"JWT upgrade failed: {resp.status_code} {resp.text}")
        except (RequestException, Timeout) as err:
            logger.error(f"JWT upgrade request failed: {err}")
            raise SCAServiceError(f"JWT upgrade request failed: {err}")
        except Exception as e:
            logger.error(f"Unexpected error during JWT upgrade: {e}")
            raise SCAServiceError(f"Unexpected error during JWT upgrade: {e}")

    def validate_sca_jwt(self, jwt_token):
        """
        Validate SCA JWT format and expiration.

        Args:
            jwt_token (str): JWT token to validate

        Returns:
            bool: True if valid, False otherwise
        """
        if not jwt_token:
            return False

        try:
            # Basic JWT structure validation
            parts = jwt_token.split('.')
            if len(parts) != 3:
                return False

            # TODO: Add proper JWT expiration validation if needed
            # For now, we rely on DTB to provide valid tokens
            return True

        except Exception as e:
            logger.error(f"JWT validation error: {e}")
            return False


class SCAServiceError(Exception):
    """Base exception class for SCAService errors."""
    pass
