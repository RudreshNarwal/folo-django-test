from datetime import timedelta

from django.http import JsonResponse
from django.utils.timezone import now
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from generics.utils.deactivate_expired_subscriptions import deactivate_expired_subscriptions
from .models import CreditReport
from . import services
from ..payments.models import Subscription


class CreditReportViewSet(viewsets.ModelViewSet):
	permission_classes = [IsAuthenticated]
	
	@action(detail=False, methods=['post'])
	def register(self, request, *args, **kwargs):
		# Check if the user is already registered
		if CreditReport.objects.filter(user=request.user, is_registered=True).exists():
			return Response({"message": "User is already registered."}, status=status.HTTP_400_BAD_REQUEST)
		
		api_response = services.register_with_tu(request.user)
		response_code = api_response.get("responseCode")
		if 200 <= response_code < 300:
			return Response(api_response, status=status.HTTP_200_OK)
		else:
			return Response(api_response, status=status.HTTP_400_BAD_REQUEST)
	
	@action(detail=False, methods=['get'])
	def check_credit_risk(self, request):
		# Checking whether the user is registered or not
		credit_report = CreditReport.objects.filter(user=request.user).order_by('-updated_on').first()
		
		if not credit_report:
			# for the case where user registration is pending
			return Response({"message": "CreditReport not found for the user."}, status=status.HTTP_404_NOT_FOUND)
			
		# First, deactivate expired subscriptions
		deactivate_expired_subscriptions(request.user)
		# Check for active subscription
		has_active_subscription = Subscription.objects.filter(user=request.user, end_date__gte=now(), is_active=True).exists()
		
		# Check if the report is older than 30 days or grade_response is empty/null
		if now() - credit_report.updated_on > timedelta(days=30) or not credit_report.grade_response:
			# Call the TU API if the condition is met
			api_response = services.fetch_credit_risk_score(request.user, credit_report)
			
			if api_response.get("responseCode") == 200:
				data = {
					"user": credit_report.user.pkid,
					"is_registered": credit_report.is_registered,
					"credit_score": credit_report.credit_score,
					"grade_response": credit_report.grade_response,
					"tlo_response": credit_report.tlo_response,
					"updated_on": credit_report.updated_on.strftime("%Y-%m-%d %H:%M:%S"),
					"has_active_subscription": has_active_subscription
				}
				return Response(data, status=status.HTTP_200_OK)
			else:
				return Response(api_response, status=status.HTTP_400_BAD_REQUEST)
		else:
			data = {
				"user": credit_report.user.pkid,
				"is_registered": credit_report.is_registered,
				"credit_score": credit_report.credit_score,
				"grade_response": credit_report.grade_response,
				"tlo_response": credit_report.tlo_response,
				"updated_on": credit_report.updated_on.strftime("%Y-%m-%d %H:%M:%S"),
				"has_active_subscription": has_active_subscription
			}
			return Response(data, status=status.HTTP_200_OK)
		
	@action(detail=False, methods=['post'])
	def email_credit_report(self, request):
		api_response = services.send_email_creditview_report(request.user)
		
		return Response(api_response, status=status.HTTP_200_OK if api_response.get("responseCode") == 200 else status.HTTP_400_BAD_REQUEST)
