import requests
import logging
import time

from django.conf import settings
from requests.exceptions import HTTPError, RequestException, Timeout

logger = logging.getLogger(__name__)


class DTBService:
    BASE_URL = 'https://api.astraafrica.co/astra-conductor/rest/v1'
    TENANT_ID = '6749'
    USERNAME = 'kmburu'
    PASSWORD = 'ubuntU*2023'

    def __init__(self):
        self.session = requests.Session()
        self.jwt_token = None
        self.session_id = None
        self.headers = {'Content-Type': 'application/json'}
        self.authenticate()

    def authenticate(self):
        """
        Authenticate once when DTBService is initialized.
        """
        url = f'{self.BASE_URL}/authentication/login'
        payload = {
            "identity": self.USERNAME,
            "password": self.PASSWORD
        }
        try:
            response = self.session.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            data = response.json()

            self.jwt_token = data['headerValue'].split(' ')[1]
            self.session_id = data['sessionId']
            self.headers['Authorization'] = data['headerValue']

            logger.debug(f"Authenticated with DTB: {self.jwt_token}")
        except HTTPError as http_err:
            resp = http_err.response
            logger.error(f"Authentication failed: {resp.status_code} {resp.text}")
            raise DTBServiceAuthenticationError(f"Authentication failed: {resp.status_code} {resp.text}")
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise DTBServiceError(f"Authentication failed: {e}")

    def renew_jwt(self):
        """
        Renew JWT if expired or invalid.
        """
        url = f'{self.BASE_URL}/authentication/renew'
        payload = {"jwt": self.jwt_token}
        try:
            response = self.session.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            data = response.json()

            self.jwt_token = data['headerValue'].split(' ')[1]
            self.session_id = data['sessionId']
            self.headers['Authorization'] = data['headerValue']

            logger.debug(f"JWT renewed: {self.jwt_token}")
        except HTTPError as http_err:
            resp = http_err.response
            logger.error(f"JWT renewal failed: {resp.status_code} {resp.text}")
            raise DTBServiceAuthenticationError(f"JWT renewal failed: {resp.status_code} {resp.text}")
        except Exception as e:
            logger.error(f"JWT renewal failed: {e}")
            raise DTBServiceError(f"JWT renewal failed: {e}")

    def request_with_retries(self, method, url, **kwargs):
        """
        Generic request method with retries and JWT renewal on 401 Unauthorized.
        """
        max_retries = 2
        backoff_factor = 1

        for attempt in range(max_retries):
            try:
                response = self.session.request(method, url, timeout=10, **kwargs)
                response.raise_for_status()
                return response
            except HTTPError as http_err:
                resp = http_err.response
                logger.error(f"HTTP error: {resp.status_code} {resp.text}")
                if resp.status_code == 401:
                    logger.debug("JWT expired or invalid. Attempting renewal.")
                    try:
                        self.renew_jwt()
                        kwargs['headers'] = self.headers
                        continue
                    except DTBServiceAuthenticationError:
                        # Cannot renew JWT; re-raise
                        raise
                else:
                    # For other HTTP errors, raise an API error
                    raise DTBServiceAPIError(resp.status_code, resp.text, error_details=resp.json())
            except (RequestException, Timeout) as err:
                logger.error(f"Request exception: {err}")
                # Retry with exponential backoff
                time.sleep(backoff_factor ** attempt)
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                raise DTBServiceError(f"Unexpected error: {e}")
        else:
            # If we exhaust all retries
            logger.error(f"Failed to {method} {url} after {max_retries} attempts.")
            raise DTBServiceError(f"Failed to {method} {url} after {max_retries} attempts.")

    def register_customer(self, customer_data):
        url = f'{self.BASE_URL}/tenants/{self.TENANT_ID}/customers'
        response = self.request_with_retries('POST', url, json=customer_data, headers=self.headers)
        return response.json()

    def add_document(self, customer_id, document_data, perform_ocr=False, validate_doc_type=False):
        url = f'{self.BASE_URL}/tenants/{self.TENANT_ID}/customers/{customer_id}/documents'
        params = {
            'performOcr': str(perform_ocr).lower(),
            'validateDocType': str(validate_doc_type).lower()
        }
        response = self.request_with_retries('POST', url, json=document_data, headers=self.headers, params=params)
        return response.json()

    def add_address(self, customer_id, address_data):
        url = f'{self.BASE_URL}/tenants/{self.TENANT_ID}/customers/{customer_id}/addresses'
        response = self.request_with_retries('POST', url, json=address_data, headers=self.headers)
        return response.json()

    def ratify_kyc(self, customer_id):
        url = f'{self.BASE_URL}/tenants/{self.TENANT_ID}/customers/{customer_id}/ratify'
        payload = {"type": "NORMAL"}
        response = self.request_with_retries('POST', url, json=payload, headers=self.headers)
        return response.json()

    def get_customer(self, customer_id):
        url = f'{self.BASE_URL}/tenants/{self.TENANT_ID}/customers/{customer_id}'
        response = self.request_with_retries('GET', url, headers=self.headers)
        return response.json()
    
    def search_customers(self, national_identity_number):
        url = f'{self.BASE_URL}/tenants/{self.TENANT_ID}/customers'
        params = {
            'nationalIdentityNumber': national_identity_number
        }
        response = self.request_with_retries('GET', url, headers=self.headers, params=params)
        return response.json()
    
    def get_wallet_types(self):
        url = f'{self.BASE_URL}/tenants/{self.TENANT_ID}/customers/{self.TENANT_ID}/wallet-types'
        response = self.request_with_retries('GET', url, headers=self.headers)
        return response.json()
    
    def create_wallet(self, customer_id, wallet_data):
        url = f'{self.BASE_URL}/tenants/{self.TENANT_ID}/customers/{customer_id}/wallets'
        response = self.request_with_retries('POST', url, json=wallet_data, headers=self.headers)
        return response.json()
    
    


class DTBServiceError(Exception):
    """Base exception class for DTBService errors."""
    pass

class DTBServiceAuthenticationError(DTBServiceError):
    """Exception raised for authentication errors."""
    pass

class DTBServiceAPIError(DTBServiceError):
    """Exception raised for API errors."""
    def __init__(self, status_code, message, error_details=None):
        self.status_code = status_code
        self.message = message
        self.error_details = error_details
        super().__init__(f"API Error {status_code}: {message}")
