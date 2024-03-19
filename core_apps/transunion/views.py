from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils.decorators import method_decorator
from rest_framework import status

from . import services
from .models import CreditReport
from .serializers import RegisterSerializer  # Ensure you import the serializer


class RegisterView(APIView):
	def post(self, request, *args, **kwargs):
		serializer = RegisterSerializer(data=request.data)
		if serializer.is_valid():
			# Use the validated data
			api_response = services.register_with_tu(serializer.validated_data)
			
			# Assuming `api_response` is a dictionary that includes a responseCode.
			if api_response.get("responseCode") == 200:
				# You can create your CreditReport object here with the serializer.validated_data
				# Example:
				# CreditReport.objects.create(**serializer.validated_data)
				return Response(api_response, status=status.HTTP_200_OK)
			else:
				return Response(api_response, status=status.HTTP_400_BAD_REQUEST)
		else:
			# Return serializer errors if validation fails
			return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

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
