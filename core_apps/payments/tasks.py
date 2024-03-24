import base64

from celery import shared_task
import requests
import json
from django.utils.timezone import now
from datetime import timedelta
from django.conf import settings

from .models import Transaction
from .services import get_access_token


@shared_task
def query_payment_status(transaction_id):
	try:
		transaction = Transaction.objects.get(pk=transaction_id)
		
		# Ensure that we only query status for transactions where a callback has not been successful
		if transaction.status not in ['Successful', 'Failed']:
			access_token, error = get_access_token()
			
			if error:
				# Trigger EMAIL to OPS TODO
			    pass

			
			headers = {
				'Authorization': f'Bearer {access_token}',
				'Content-Type': 'application/json',
			}
			
			# Assuming you have a way to generate these dynamically or retrieve from transaction
			business_short_code = settings.MPESA_BUSINESS_CODE
			passkey = settings.MPESA_PASSKEY
			timestamp = transaction.mpesa_timestamp
			password = base64.b64encode(f"{business_short_code}{passkey}{timestamp}".encode()).decode('utf-8')
			checkout_request_id = transaction.mpesa_checkout_request_id
			
			data = {
				"BusinessShortCode": business_short_code,
				"Password": password,
				"Timestamp": timestamp,
				"CheckoutRequestID": checkout_request_id
			}
			
			response = requests.post('https://sandbox.safaricom.co.ke/mpesa/stkpushquery/v1/query', json=data, headers=headers)
			if response.status_code == 200:
				response_data = response.json()
				# Update transaction status based on the response
				transaction.response = {"from": "Status Api", **response_data}
				transaction.status = 'Successful' if response_data.get("ResponseCode") == "0" else 'Failed'
				transaction.save()
			else:
				# Handle unsuccessful API call
				pass
	except Transaction.DoesNotExist:
		# Handle the case where the transaction does not exist
		pass
