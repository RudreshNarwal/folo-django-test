import base64
import requests
from datetime import datetime

from django.conf import settings


def get_access_token():
	"""Function to call the external service and get an access token."""
	try:
		response = requests.get(
			'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials',
			headers={
				'Authorization': f'Basic {settings.MPESA_CLIENT_TOKEN}',
			}
		)
		response.raise_for_status()  # Raises an HTTPError if the response code was unsuccessful
		return response.json().get('access_token'), None
	except requests.exceptions.RequestException as e:
		# Return None and the error
		return None, e


def make_stk_push_request(access_token, transaction):
	headers = {
		'Authorization': f'Bearer {access_token}',
		'Content-Type': 'application/json',
	}
	
	# Generate the timestamp and password as per M-PESA API requirements
	timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
	business_short_code = settings.MPESA_BUSINESS_CODE
	passkey = settings.MPESA_PASSKEY
	password = base64.b64encode(f"{business_short_code}{passkey}{timestamp}".encode()).decode('utf-8')
	callback_url = f"{settings.BASE_URL}/api/v1/mpesa/callback/"  # Replace with your callback URL
	
	data = {
		"BusinessShortCode": business_short_code,
		"Password": password,
		"Timestamp": timestamp,
		"TransactionType": "CustomerPayBillOnline",
		"Amount": transaction.get_amount_as_int(),
		"PartyA": transaction.user.get_mobile_without_plus,  # Your business's party number
		"PartyB": business_short_code,
		"PhoneNumber": transaction.user.get_mobile_without_plus,  # Assuming user model has a phone_number field
		"CallBackURL": callback_url,
		"AccountReference": "FOLO MONEY",
		"TransactionDesc": "Credit Report Subscription"
	}
	
	response = requests.post('https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest', json=data, headers=headers)
	
	if response.status_code == 200:
		response_body = response.json()
		if response_body.get("ResponseCode") == "0":
			return {
				"merchant_request_id": response_body.get("MerchantRequestID"),
				"checkout_request_id": response_body.get("CheckoutRequestID"),
				"timestamp": timestamp,
				"status": "Pending"
			}, None
		else:
			return {
				"merchant_request_id": response_body.get("MerchantRequestID"),
				"checkout_request_id": response_body.get("CheckoutRequestID"),
				"status": "Failed",
				"timestamp": timestamp,
				"response_body": response_body
			}, None
	return None, response.text

