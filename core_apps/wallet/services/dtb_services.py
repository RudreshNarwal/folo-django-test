import requests
import logging
from django.conf import settings
from requests.exceptions import HTTPError, RequestException, Timeout
import time

logger = logging.getLogger(__name__)

class DTBService:
    BASE_URL = 'https://api.astraafrica.co/dev/test-conductor/rest/v1'
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
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise

    def request_with_retries(self, method, url, **kwargs):
        max_retries = 2
        backoff_factor = 1
        for attempt in range(max_retries):
            try:
                response = self.session.request(method, url, timeout=10, **kwargs)
                response.raise_for_status()
                return response
            except HTTPError as http_err:
                logger.error(f"HTTP error occurred: {http_err}")
                response = http_err.response
                if response.status_code == 401:
                    logger.debug("JWT expired, attempting to renew.")
                    self.renew_jwt()
                    kwargs['headers'] = self.headers
                    continue
                if 400 <= response.status_code < 500:
                    break
                elif 500 <= response.status_code < 600:
                    pass
            except (RequestException, Timeout) as err:
                logger.error(f"Request error occurred: {err}")
            sleep_time = backoff_factor ** attempt
            time.sleep(sleep_time)
        else:
            logger.error(f"Failed to {method} {url} after {max_retries} attempts.")
            raise Exception(f"Failed to {method} {url} after {max_retries} attempts.")

    def renew_jwt(self):
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
        except Exception as e:
            logger.error(f"JWT renewal failed: {e}")
            raise

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

    def ratify_kyc(self, customer_id):
        url = f'{self.BASE_URL}/tenants/{self.TENANT_ID}/customers/{customer_id}/ratify'
        payload = {"type": "NORMAL"}
        response = self.request_with_retries('POST', url, json=payload, headers=self.headers)
        return response.json()

    def add_address(self, customer_id, address_data):
        url = f'{self.BASE_URL}/tenants/{self.TENANT_ID}/customers/{customer_id}/addresses'
        response = self.request_with_retries('POST', url, json=address_data, headers=self.headers)
        return response.json()

    def get_customer(self, customer_id):
        url = f'{self.BASE_URL}/tenants/{self.TENANT_ID}/customers/{customer_id}'
        response = self.request_with_retries('GET', url, headers=self.headers)
        return response.json()
