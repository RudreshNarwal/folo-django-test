# transunion/services/api_service.py

import requests
from django.contrib.auth import get_user_model
from django.conf import settings


def register_with_tu(data):
	url = "https://secure3.crbafrica.com/crbws/rest/nipashe_indirect/ke/register"
	headers = {"Content-Type": "application/json", 'Authorization': 'Basic S0VGcTdORTN2ejpQbk5lR1VjQmR4MEVNSg=='}
	data.update({
		"username": settings.TRANSUNION_UAT_USERNAME,
		"password": settings.TRANSUNION_UAT_PASSWORD,
		"code": settings.TRANSUNION_UAT_CODE,
		"infinityCode": settings.TRANSUNION_UAT_INFINITY_CODE,
		"reportReason": data.get('report_reason'),
		"reportSector": data.get('report_sector'),
		"names": "Surname397208832 OtherNames397208832",
		"documentNumber": data.get('document_number'),
		"telephoneMobile": data.get('telephone_mobile')
	})
	response = requests.post(url, json=data, headers=headers)
	return response.json()


def fetch_credit_risk_score(data):
	url = "https://secure3.crbafrica.com/crbws/rest/nipashe_indirect/ke/credit_risk_score"
	headers = {"Content-Type": "application/json"}
	# Add authentication and other required info to the data
	data.update({
		"username": settings.TRANSUNION_UAT_USERNAME,
		"password": settings.TRANSUNION_UAT_PASSWORD,
		"code": settings.TRANSUNION_UAT_CODE,
	})
	response = requests.post(url, json=data, headers=headers)
	return response.json()


def fetch_total_outstanding_loan(data):
	url = "https://secure3.crbafrica.com/crbws/rest/nipashe_indirect/ke/total_outstanding_loan"
	headers = {"Content-Type": "application/json"}
	
	# It's advisable to use Django's settings for sensitive credentials
	data.update({
		"username": settings.TRANSUNION_USERNAME,
		"password": settings.TRANSUNION_PASSWORD,
		"code": settings.TRANSUNION_CODE,
		"infinityCode": settings.TRANSUNION_INFINITY_CODE,
	})
	
	response = requests.post(url, json=data, headers=headers)
	return response.json()


def send_email_creditview_report(data):
	url = "https://secure3.crbafrica.com/crbws/rest/nipashe_indirect/ke/email_creditview_report"
	headers = {"Content-Type": "application/json"}
	
	data.update({
		"username": settings.TRANSUNION_USERNAME,
		"password": settings.TRANSUNION_PASSWORD,
		"code": settings.TRANSUNION_CODE,
		"infinityCode": settings.TRANSUNION_INFINITY_CODE,
	})
	
	response = requests.post(url, json=data, headers=headers)
	return response.json()
