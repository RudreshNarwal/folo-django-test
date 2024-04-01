# transunion/services/api_service.py

import requests
from django.contrib.auth import get_user_model
from django.conf import settings

from core_apps.transunion.models import CreditReport


def register_with_tu(user):
	url = "https://secure3.crbafrica.com/crbws/rest/nipashe_indirect/ke/register"
	headers = {"Content-Type": "application/json", 'Authorization': 'Basic S0VGcTdORTN2ejpQbk5lR1VjQmR4MEVNSg=='}
	data = {}
	data.update({
		"username": settings.TRANSUNION_UAT_USERNAME,
		"password": settings.TRANSUNION_UAT_PASSWORD,
		"code": settings.TRANSUNION_UAT_CODE,
		"infinityCode": settings.TRANSUNION_UAT_INFINITY_CODE,
		"reportReason": 1,
		"reportSector": 1,
		"names": f"{user.last_name} {user.first_name}",
		"documentNumber": user.nation_id,
		"telephoneMobile": user.get_mobile_without_plus
	})
	response = requests.post(url, json=data, headers=headers)
	api_response = response.json()
	response_code = api_response.get("responseCode")
	
	if 200 <= response_code < 300:
		CreditReport.objects.create(user=user, is_registered=True)
	
	return api_response


def fetch_credit_risk_score(user, credit_report):
	url = "https://secure3.crbafrica.com/crbws/rest/nipashe_indirect/ke/credit_risk_score"
	headers = {
		"Content-Type": "application/json",
		'Authorization': 'Basic S0VGcTdORTN2ejpQbk5lR1VjQmR4MEVNSg=='
	}
	data = {
		"username": settings.TRANSUNION_UAT_USERNAME,
		"password": settings.TRANSUNION_UAT_PASSWORD,
		"code": settings.TRANSUNION_UAT_CODE,
		"infinityCode": settings.TRANSUNION_UAT_INFINITY_CODE,
		"reportReason": 2,
		"reportSector": 1,
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
	url = "https://secure3.crbafrica.com/crbws/rest/nipashe_indirect/ke/total_outstanding_loan"
	headers = {
		"Content-Type": "application/json",
		'Authorization': 'Basic S0VGcTdORTN2ejpQbk5lR1VjQmR4MEVNSg=='
	}
	data = {}
	data.update({
		"username": settings.TRANSUNION_UAT_USERNAME,
		"password": settings.TRANSUNION_UAT_PASSWORD,
		"code": settings.TRANSUNION_UAT_CODE,
		"infinityCode": settings.TRANSUNION_UAT_INFINITY_CODE,
		"reportReason": 2,
		"reportSector": 1,
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
	url = "https://secure3.crbafrica.com/crbws/rest/nipashe_indirect/ke/email_creditview_report"
	headers = {
		"Content-Type": "application/json",
		"Authorization": 'Basic S0VGcTdORTN2ejpQbk5lR1VjQmR4MEVNSg=='
	}
	data = {}
	data.update({
		"username": settings.TRANSUNION_UAT_USERNAME,
		"password": settings.TRANSUNION_UAT_PASSWORD,
		"code": settings.TRANSUNION_UAT_CODE,
		"infinityCode": settings.TRANSUNION_UAT_INFINITY_CODE,
		"reportReason": 2,
		"reportSector": 1,
		"name1": user.first_name,
		"name2": user.last_name,
		"nationalId": user.nation_id,
		"telephoneMobile": user.get_mobile_without_plus,
		"emailAddress": user.email
	})
	
	response = requests.post(url, json=data, headers=headers)
	return response.json()
