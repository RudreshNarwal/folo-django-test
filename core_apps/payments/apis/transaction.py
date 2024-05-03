import json

from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse

from core_apps.payments.models import Transaction
from ..serializers.transaction import TransactionSerializer, TransactionCreateSerializer
from core_apps.payments.services.mpesa import get_access_token, make_stk_push_request
from core_apps.payments.services.subscription import create_registration_for_tu, create_subscription
from core_apps.payments.tasks import query_payment_status
from rest_framework import viewsets


class UserTransactionsListView(APIView):
	permission_classes = [IsAuthenticated]

	def get(self, request):
		transactions = Transaction.objects.filter(user=request.user).order_by('-created_on')
		serializer = TransactionSerializer(transactions, many=True)
		return Response(serializer.data, status=status.HTTP_200_OK)


class TransactionDetailView(APIView):
	permission_classes = [IsAuthenticated]  # Ensure the user is authenticated

	def get(self, request, transaction_id):
		try:
			# Ensuring: transaction belongs to the request.user
			transaction = Transaction.objects.get(pk=transaction_id, user=request.user)
			serializer = TransactionSerializer(transaction)
			return Response(serializer.data)
		except Transaction.DoesNotExist:
			return Response({'message': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)


class InitiateTransactionAPIView(APIView):
	permission_classes = [IsAuthenticated]
	
	def post(self, request, *args, **kwargs):
		serializer = TransactionCreateSerializer(data=request.data)
		if serializer.is_valid():
			# The amount is included in the serializer and will be part of the serializer.save()
			transaction = serializer.save(
				user=request.user,
				status='Initiated'
			)
			
			# Celery task
			transaction_id = transaction.pkid
			# Schedule the task to run after 180 seconds
			query_payment_status.apply_async((transaction_id,), countdown=91)
			
			# Use the utility function to get the access token
			access_token, error = get_access_token()
			if error:
				transaction.status = 'Failed'
				transaction.response = {"error": error}
				transaction.save(update_fields=['status', 'response'])
				return Response({"message": "Failed to retrieve access token", "details": str(error)},
				                status=status.HTTP_500_INTERNAL_SERVER_ERROR)
			
			stk_response, error = make_stk_push_request(access_token, transaction)
			if error:
				transaction.status = 'Failed'
				transaction.response = {"error": error}
				transaction.save(update_fields=['status', 'response'])
				return Response({"message": "Failed to retrieve access token", "details": str(error)},
				                status=status.HTTP_500_INTERNAL_SERVER_ERROR)
			
			transaction.status = stk_response["status"]
			transaction.mpesa_merchant_request_id = stk_response["merchant_request_id"]
			transaction.mpesa_checkout_request_id = stk_response["checkout_request_id"]
			transaction.mpesa_timestamp = stk_response["timestamp"]
			if stk_response["status"] == "Failed":
				transaction.response = stk_response["response_body"]
			transaction.save()
			
			return Response(
				{"message": "Transaction initiated successfully.", "transaction_id": transaction.pkid},
				status=status.HTTP_201_CREATED)
		
		else:
			return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MpesaCallbackAPIView(APIView):
	permission_classes = [AllowAny]
	
	def post(self, request, *args, **kwargs):
		try:
			callback_data = json.loads(request.body)
			body = callback_data.get('Body', {})
			stk_callback = body.get('stkCallback', {})
			merchant_request_id = stk_callback.get('MerchantRequestID')
			checkout_request_id = stk_callback.get('CheckoutRequestID')
			result_code = stk_callback.get('ResultCode')
			
			# Find the transaction by MerchantRequestID and CheckoutRequestID
			transaction = Transaction.objects.filter(
				mpesa_merchant_request_id=merchant_request_id,
				mpesa_checkout_request_id=checkout_request_id
			).first()
			
			if transaction:
				# Update transaction status based on ResultCode
				transaction.status = 'Successful' if str(result_code) == "0" else 'Failed'
				if str(result_code) == "0":
					# Process success callback to get MpesaReceiptNumber
					callback_metadata = stk_callback.get('CallbackMetadata', {})
					for item in callback_metadata.get('Item', []):
						if item.get('Name') == 'MpesaReceiptNumber':
							transaction.mpesa_receipt_number = item.get('Value')
							break
					
					# New: Check if the plan is a subscription and create a subscription
					if transaction.plan and transaction.plan.type == 'Subscription':
						create_registration_for_tu(request.user)
						create_subscription(transaction)
				
				# Save the whole response for record-keeping regardless of success or failure
				transaction.response = callback_data
				transaction.save()
				
				return JsonResponse({'status': 'success', 'message': 'Callback processed successfully'})
			else:
				return JsonResponse({'status': 'error', 'message': 'Transaction not found'}, status=404)
		
		except Exception as e:
			return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
