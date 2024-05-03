import base64
from celery import shared_task
import requests
from django.conf import settings
from .models import Transaction, User
from .services.mpesa import get_access_token
from .services.subscription import create_registration_for_tu, create_subscription
from ..transunion.services import register_with_tu
import logging


@shared_task
def query_payment_status(transaction_id):
	try:
		transaction = Transaction.objects.get(pk=transaction_id)
		
		# Only query status for transactions that haven't received a final callback
		if transaction.status not in ['Successful', 'Failed']:
			access_token, error = get_access_token()
			
			if error:
				logging.error(f"Error getting access token: {error}")
				return
			
			headers = {
				'Authorization': f'Bearer {access_token}',
				'Content-Type': 'application/json',
			}
			
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
			
			response = requests.post(f"{settings.MPESA_ENDPOINT}/mpesa/stkpushquery/v1/query", json=data, headers=headers)
			if response.status_code == 200:
				response_data = response.json()
				transaction.response = {"from": "Status Api", **response_data}
				if str(response_data.get("ResultCode")) == "0":
					transaction.status = 'Successful'
					if transaction.plan and transaction.plan.type == 'Subscription':
						user = User.objects.get(pk=transaction.user_id)
						create_registration_for_tu(user)
						create_subscription(transaction)
				else:
					transaction.status = 'Failed'
				transaction.save()
	except Transaction.DoesNotExist:
		logging.info(f"Transaction doesn't exist {transaction.id}")
		pass
