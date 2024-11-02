import base64
from celery import shared_task
import requests
from django.conf import settings
from .models import Transaction, User
from .services.mpesa import get_access_token
from .services.subscription import create_registration_for_tu, create_subscription
from ..transunion.services import register_with_tu
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=20)
def query_payment_status(self, transaction_id):
	try:
		transaction = Transaction.objects.get(pk=transaction_id)
		
		# Only query status for transactions that haven't received a final callback
		if transaction.status not in ['Successful', 'Failed']:
			access_token, error = get_access_token()
			
			if error:
				logger.error(f"Error getting access token: {error}")
				raise self.retry(exc=Exception(error))
			
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
					transaction.save()
					if transaction.plan and transaction.plan.type == 'Subscription':
						user = User.objects.get(pk=transaction.user_id)
						create_registration_for_tu(user)
						create_subscription(transaction)
				else:
					transaction.status = 'Failed'
					transaction.save()
					# Retry task if status is still Pending after an API call
					if response_data.get("ResultCode") == "1":  # Assuming '1' means Pending
						raise self.retry()
				return "Transaction updated successfully"
			else:
				logger.error(f"Error querying payment status: HTTP {response.status_code}")
				raise self.retry(exc=response.status_code)
		else:
			return "No action needed, transaction already completed."
	
	except Transaction.DoesNotExist:
		logger.info(f"Transaction with ID {transaction_id} doesn't exist")
	except Exception as e:
		logger.error(f"Unexpected error occurred: {str(e)}")
		raise self.retry(exc=e)
