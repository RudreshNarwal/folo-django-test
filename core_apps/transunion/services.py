# transunion/services/api_service.py

import requests
from django.contrib.auth import get_user_model
from django.conf import settings

def register_with_third_party_api(data):
    url = "https://secure3.crbafrica.com/crbws/rest/nipashe_indirect/ke/register"
    headers = {"Content-Type": "application/json"}
    data.update({
        "username": settings.TRANSUNION_UAT_USERNAME,
        "password": settings.TRANSUNION_UAT_PASSWORD,
        "code": settings.TRANSUNION_UAT_CODE,
        "infinityCode": settings.TRANSUNION_UAT_INFINITY_CODE,
    })
    response = requests.post(url, json=data, headers=headers)
    return response.json()
