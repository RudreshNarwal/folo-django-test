import requests
import logging
import time
import re

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
            response = self.session.post(url, json=payload, headers=self.headers, verify=True)
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

    def upgrade_jwt_for_sca(self, intent_id, otp):
        """
        Upgrade JWT using SCA credentials (OTP verification).
        Based on DTB API documentation for SCA step-up authentication.
        
        The upgraded JWT is specifically bound to the intent and can only be used
        to resubmit the original request (with IDENTICAL path and body).
        
        Note: The upgraded JWT must be used within 3 minutes of the SCA challenge.
        
        Args:
            intent_id (str): SCA intent ID from challenge response header
            otp (str): One-time password from user (use "911911" in sandbox)
            
        Returns:
            str: Upgraded JWT token
            
        Raises:
            DTBServiceError: If JWT upgrade fails
        """
        # Correct endpoint from DTB documentation: PUT /authentication/jwt
        url = f'{self.BASE_URL}/authentication/jwt'
        
        # Payload format from documentation
        payload = {
            "intentId": intent_id,
            "jwt": self.jwt_token,  # Current JWT
            "otp": otp
        }
        
        try:
            logger.info(f"Upgrading JWT for SCA with intentId: {intent_id}")
            logger.debug(f"SCA upgrade request payload: {{'intentId': '{intent_id}', 'jwt': '***', 'otp': '***'}}")
            
            # Use PUT method as per DTB documentation
            response = self.session.put(
                url,
                json=payload,
                headers=self.headers,
                timeout=10,
                verify=True
            )
            response.raise_for_status()
            
            data = response.json()
            
            if 'headerValue' not in data:
                raise DTBServiceError("Invalid response from DTB auth service: missing headerValue")
            
            # Extract upgraded JWT
            upgraded_jwt = data['headerValue'].split(' ')[1]
            
            # Update internal state with upgraded JWT
            self.jwt_token = upgraded_jwt
            self.headers['Authorization'] = data['headerValue']
            if 'sessionId' in data:
                self.session_id = data['sessionId']
            
            logger.info(f"JWT successfully upgraded for SCA intent: {intent_id}")
            
            return upgraded_jwt
            
        except HTTPError as http_err:
            resp = http_err.response
            logger.error(f"JWT upgrade failed: {resp.status_code} {resp.text}")
            raise DTBServiceError(f"JWT upgrade failed: {resp.status_code} {resp.text}")
        except (RequestException, Timeout) as err:
            logger.error(f"JWT upgrade request failed: {err}")
            raise DTBServiceError(f"JWT upgrade request failed: {err}")
        except Exception as e:
            logger.error(f"Unexpected error during JWT upgrade: {e}")
            raise DTBServiceError(f"Unexpected error during JWT upgrade: {e}")

    def request_with_retries(self, method, url, **kwargs):
        """
        Generic request method with retries, JWT renewal on 401, and SCA challenge handling on 403.
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
                elif resp.status_code == 403:
                    # Check if this is an SCA challenge
                    sca_challenge = self.parse_sca_challenge(resp)
                    if sca_challenge:
                        logger.debug(f"SCA challenge detected: {sca_challenge}")
                        raise DTBServiceSCAChallengeError(
                            f"SCA challenge required: {sca_challenge['sca_type']}",
                            sca_challenge=sca_challenge
                        )
                    else:
                        # 403 but not SCA challenge
                        raise DTBServiceAPIError(resp.status_code, resp.text, error_details=resp.json())
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
    
    def get_wallets(self, customer_id):
        url = f'{self.BASE_URL}/tenants/{self.TENANT_ID}/customers/{customer_id}/wallets'
        response = self.request_with_retries('GET', url, headers=self.headers)
        return response.json()
    
    def initiate_top_up(self, payload):
        url = f'{self.BASE_URL}/tenants/{self.TENANT_ID}/payments'
        response = self.request_with_retries('POST', url, json=payload, headers=self.headers)
        return response.json()
    
    def get_top_up_status(self, wallet_id, payment_id):
        url = f'{self.BASE_URL}/tenants/{self.TENANT_ID}/wallets/{wallet_id}/topups/{payment_id}'
        response = self.request_with_retries('GET', url, headers=self.headers)
        return response.json()
    
    def get_wallet_details(self, wallet_id):
        url = f'{self.BASE_URL}/tenants/{self.TENANT_ID}/wallets/{wallet_id}'
        response = self.request_with_retries('GET', url, headers=self.headers)
        return response.json()
        
    def wallet_to_wallet_transfer(self, payload):
        """
        Transfer funds from one wallet to another wallet
        
        Payload should include:
        - amount: Amount to transfer
        - description: Description of the transfer
        - externalId: External ID for the transaction (optional)
        - externalUniqueId: Unique ID for the transaction
        - fromWalletId: Source wallet ID
        - toWalletId: Destination wallet ID
        """
        url = f'{self.BASE_URL}/tenants/{self.TENANT_ID}/wallets/transfers'
        response = self.request_with_retries('POST', url, json=payload, headers=self.headers)
        return response.status_code
        
    def wallet_to_mpesa_transfer(self, wallet_id, payload):
        """
        Transfer funds from wallet to MPESA
        
        Payload should include:
        - deliverToPhone: Phone number to send money to
        - reference: Reference for the transaction
        - amount: Amount to transfer
        - callbackUrl: URL for callback notifications
        - description: Description of the transaction
        - type: Type of transfer (e.g., KE_DTB_MPESA)
        - externalUniqueId: Unique ID for the transaction
        """
        url = f'{self.BASE_URL}/tenants/{self.TENANT_ID}/wallets/{wallet_id}/withdrawals'
        response = self.request_with_retries('POST', url, json=payload, headers=self.headers)
        return response.json()
        
    def get_withdrawal_status(self, wallet_id, withdrawal_id):
        """
        Get the status of a specific withdrawal.
        Note: This uses the top-ups endpoint as a workaround, assuming withdrawal IDs
        are treated similarly to payment IDs for status checks.
        """
        # The endpoint for checking withdrawal status is the same as for topups,
        # using the withdrawal_id as the payment_id in the URL.
        url = f'{self.BASE_URL}/tenants/{self.TENANT_ID}/wallets/{wallet_id}/topups/{withdrawal_id}'
        response = self.request_with_retries('GET', url, headers=self.headers)
        return response.json()
        
    def get_withdrawal_fee(self, wallet_id, amount, withdrawal_type="KE_DTB_MPESA"):
        """
        Get the fee for a specific withdrawal amount and type
        
        Parameters:
        - wallet_id: ID of the wallet
        - amount: Amount to withdraw
        - withdrawal_type: Type of withdrawal (default: KE_DTB_MPESA)
        
        Returns a dict with 'feeAmount' key
        """
        url = f'{self.BASE_URL}/tenants/{self.TENANT_ID}/wallets/{wallet_id}/withdrawals/fees'
        params = {
            'amount': amount,
            'type': withdrawal_type
        }
        response = self.request_with_retries('GET', url, headers=self.headers, params=params)
        return response.json()
    
    def wallet_to_pesalink_transfer(self, wallet_id, payload):
        """
        Transfer funds from wallet to bank account via PesaLink
        
        Payload should include:
        - amount: Amount to transfer
        - type: "KE_DTB_PESALINK"
        - description: Description of the transaction
        - externalUniqueId: Unique ID for the transaction
        - accountNumber: Bank account number
        - branchCode: Branch code
        - accountCurrency: Account currency (e.g., "KES")
        - bank: Bank code
        - reference: Reference for the transaction
        - callbackUrl: URL for callback notifications
        """
        url = f'{self.BASE_URL}/tenants/{self.TENANT_ID}/wallets/{wallet_id}/withdrawals'
        response = self.request_with_retries('POST', url, json=payload, headers=self.headers)
        return response.json()
        
    def wallet_to_eft_transfer(self, wallet_id, payload):
        """
        Transfer funds from wallet to bank account via EFT
        
        Payload should include:
        - accountName: Account holder name
        - accountNumber: Bank account number
        - branchCode: Branch code
        - bankCode: Bank code
        - amount: Amount to transfer
        - callbackUrl: URL for callback notifications
        - deliverToPhone: Phone number (optional)
        - description: Description of the transaction
        - externalUniqueId: Unique ID for the transaction
        - location: Location (e.g., "kenya")
        - reference: Reference for the transaction
        - type: "KE_DTB_EFT"
        - currency: Currency (e.g., "KES")
        """
        url = f'{self.BASE_URL}/tenants/{self.TENANT_ID}/wallets/{wallet_id}/withdrawals'
        response = self.request_with_retries('POST', url, json=payload, headers=self.headers)
        return response.json()
        
    def get_bank_transfer_fee(self, wallet_id, amount, transfer_type="KE_DTB_PESALINK"):
        """
        Get the fee for a specific bank transfer amount and type
        
        Parameters:
        - wallet_id: ID of the wallet
        - amount: Amount to transfer
        - transfer_type: Type of transfer (KE_DTB_PESALINK or KE_DTB_EFT)
        
        Returns a dict with 'feeAmount' key
        """
        url = f'{self.BASE_URL}/tenants/{self.TENANT_ID}/wallets/{wallet_id}/withdrawals/fees'
        params = {
            'amount': amount,
            'type': transfer_type
        }
        response = self.request_with_retries('GET', url, headers=self.headers, params=params)
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


class DTBServiceSCAChallengeError(DTBServiceError):
    """Exception raised when DTB requires SCA challenge."""
    def __init__(self, message, sca_challenge=None):
        self.sca_challenge = sca_challenge
        super().__init__(message)
