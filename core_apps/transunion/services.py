# transunion/services/api_service.py
import logging

import requests
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.mail import mail_admins, send_mail

from core_apps.transunion.models import CreditReport


def register_with_tu(user):
	url = f"{settings.TRANSUNION_ENDPOINT}/register"
	headers = {
		"Content-Type": "application/json",
	}
	data = {
		"username": settings.TRANSUNION_USERNAME,
		"password": settings.TRANSUNION_PASSWORD,
		"code": settings.TRANSUNION_CODE,
		"infinityCode": settings.TRANSUNION_INFINITY_CODE,
		"reportReason": 13,
		"reportSector": 2,
		"names": f"{user.last_name} {user.first_name}",
		"documentNumber": user.nation_id,
		"telephoneMobile": user.get_mobile_without_plus,
	}
	
	response = requests.post(url, json=data, headers=headers)
	api_response = response.json()
	response_code = api_response.get("responseCode")
	
	if 200 <= response_code < 300:
		CreditReport.objects.create(user=user, is_registered=True)
	else:
		error_message = f"Failed to register with TU. Response Code: {response_code}, User: {user.get_mobile_without_plus}. Also, update user subscription as playment was successful"
		logging.error(error_message)
		# Send email to admins
		send_mail(
			subject="TransUnion Registration Failed",
			message=error_message,
			from_email=settings.DEFAULT_FROM_EMAIL,
			recipient_list=settings.DEFAULT_EMAIL_RECEIVERS,
			fail_silently=False,
		)
	
	return api_response


def fetch_credit_risk_score(user, credit_report):
	url = f"{settings.TRANSUNION_ENDPOINT}/credit_risk_score"
	headers = {
		"Content-Type": "application/json",
	}
	data = {
		"username": settings.TRANSUNION_USERNAME,
		"password": settings.TRANSUNION_PASSWORD,
		"code": settings.TRANSUNION_CODE,
		"infinityCode": settings.TRANSUNION_INFINITY_CODE,
		"reportReason": 13,
		"reportSector": 2,
		"name1": user.first_name,
		"name2": user.last_name,
		"nationalId": user.nation_id,
		"telephoneMobile": user.get_mobile_without_plus
	}
	
	try:
		response = requests.post(url, json=data, headers=headers)
		response.raise_for_status()
		grade_response = response.json()
		
		tlo_response = fetch_total_outstanding_loan(user)
		send_email_creditview_report(user)
		
		if grade_response.get("responseCode") == 200:
			credit_report.grade_response = grade_response.get("data")
			credit_report.tlo_response = tlo_response
			credit_report.save(update_fields=["grade_response", "tlo_response", "updated_on", "updated_by"])
			return grade_response
	except requests.exceptions.RequestException as e:
		# Consider logging the error properly using Django's logging framework
		print(e)
		return {"responseCode": 400, "message": "An error occurred while fetching the credit risk score."}


def fetch_total_outstanding_loan(user):
	url = f"{settings.TRANSUNION_ENDPOINT}/total_outstanding_loan"
	headers = {
		"Content-Type": "application/json",
		# 'Authorization': 'Basic S0VGcTdORTN2ejpQbk5lR1VjQmR4MEVNSg=='
	}
	data = {}
	data.update({
		"username": settings.TRANSUNION_USERNAME,
		"password": settings.TRANSUNION_PASSWORD,
		"code": settings.TRANSUNION_CODE,
		"infinityCode": settings.TRANSUNION_INFINITY_CODE,
		"reportReason": 13,
		"reportSector": 2,
		"name1": user.first_name,
		"name2": user.last_name,
		"nationalId": user.nation_id,
		"telephoneMobile": user.get_mobile_without_plus
	})
	
	try:
		response = requests.post(url, json=data, headers=headers)
		response.raise_for_status()
		api_response = response.json()
		
		if api_response.get("responseCode") == 200:
			return api_response.get("data")
	
	except requests.exceptions.RequestException as e:
		print(e)
		return {"responseCode": 400, "message": "An error occurred while fetching the total outstanding loan."}


def send_email_creditview_report(user):
	url = f"{settings.TRANSUNION_ENDPOINT}/email_creditview_report"
	headers = {
		"Content-Type": "application/json",
	}
	data = {}
	data.update({
		"username": settings.TRANSUNION_USERNAME,
		"password": settings.TRANSUNION_PASSWORD,
		"code": settings.TRANSUNION_CODE,
		"infinityCode": settings.TRANSUNION_INFINITY_CODE,
		"reportReason": 13,
		"reportSector": 2,
		"name1": user.first_name,
		"name2": user.last_name,
		"nationalId": user.nation_id,
		"telephoneMobile": user.get_mobile_without_plus,
		"emailAddress": user.email
	})
	
	response = requests.post(url, json=data, headers=headers)
	return response.json()
