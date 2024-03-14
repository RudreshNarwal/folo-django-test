from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils.decorators import method_decorator
from rest_framework import status

from . import services
from .models import CreditReport


class RegisterView(APIView):
	def post(self, request, *args, **kwargs):
		# Here, it's assumed that the request's content type is 'application/json'
		# and thus, `request.data` will contain the parsed JSON data.
		data = request.data
		
		# Call the 3rd party API with the provided data.
		api_response = services.register_with_third_party_api(data)
		
		CreditReport.objects.create(
		
		)
		
		# Return the API response. You might adjust the status code based on the actual
		# API response or any other logic you have in place.
		return Response(api_response, status=status.HTTP_200_OK if api_response.get("responseCode") == 200 else status.HTTP_400_BAD_REQUEST)


class CheckCreditRiskScoreView(APIView):
	permission_classes = [IsAuthenticated]
	
	def post(self, request, *args, **kwargs):
		# Convert QueryDict to dictionary
		data = request.data
		
		# Call your service layer
		api_response = services.fetch_credit_risk_score(data)
		
		CreditReport.objects.update(
		
		)
		
		return Response(api_response, status=status.HTTP_200_OK if api_response.get("responseCode") == 200 else status.HTTP_400_BAD_REQUEST)


class CheckTotalOutstandingLoanView(APIView):
	permission_classes = [IsAuthenticated]
	
	def post(self, request, *args, **kwargs):
		data = request.data.copy()
		api_response = services.fetch_total_outstanding_loan(data)
		
		CreditReport.objects.update(
		
		)
		
		return Response(api_response, status=status.HTTP_200_OK if api_response.get("responseCode") == 200 else status.HTTP_400_BAD_REQUEST)


class EmailCreditViewReportView(APIView):
	permission_classes = [IsAuthenticated]
	
	def post(self, request, *args, **kwargs):
		data = request.data.copy()
		api_response = services.send_email_creditview_report(data)
		
		return Response(api_response, status=status.HTTP_200_OK if api_response.get("responseCode") == 200 else status.HTTP_400_BAD_REQUEST)
