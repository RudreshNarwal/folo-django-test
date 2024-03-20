from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import CreditReport
from .serializers import CreditReportSerializer
from . import services

class CreditReportViewSet(viewsets.ModelViewSet):
    serializer_class = CreditReportSerializer
    permission_classes = [IsAuthenticated]
    
    # def get_queryset(self):
	#     # Return only the reports belonging to the current user
	#     return CreditReport.objects.filter(user=self.request.user)
    #
    # def perform_create(self, serializer):
    #     # Custom logic before saving can go here
    #     super().perform_create(serializer)
    #     # Custom logic after saving can go here
    
    @action(detail=False, methods=['post'])
    def register(self, request, *args, **kwargs):
	    serializer = CreditReportSerializer(data=request.data)
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
    
    @action(detail=True, methods=['post'])
    def check_credit_risk(self, request, pk=None):
	    # Convert QueryDict to dictionary
	    data = request.data
	    # Call your service layer
	    api_response = services.fetch_credit_risk_score(data)
	    CreditReport.objects.update()
	    return Response(api_response, status=status.HTTP_200_OK if api_response.get("responseCode") == 200 else status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def check_total_outstanding_loan(self, request, pk=None):
	    data = request.data.copy()
	    api_response = services.fetch_total_outstanding_loan(data)
	    
	    CreditReport.objects.update()
	    return Response(api_response, status=status.HTTP_200_OK if api_response.get("responseCode") == 200 else status.HTTP_400_BAD_REQUEST)
    
    
    @action(detail=True, methods=['post'])
    def email_credit_report(self, request, pk=None):
	    data = request.data.copy()
	    api_response = services.send_email_creditview_report(data)
	    
	    return Response(api_response, status=status.HTTP_200_OK if api_response.get("responseCode") == 200 else status.HTTP_400_BAD_REQUEST)


# Adapt your EmailCreditViewReportView.post logic here
	    
	    

class RegisterView(APIView):
	def post(self, request, *args, **kwargs):
		serializer = CreditReportSerializer(data=request.data)
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
