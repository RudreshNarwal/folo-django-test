# import os
# import re
# import uuid
#
# import requests
# import json
# from uno import settings
#
# # PAN card validation method
# from django.db.migrations import serializer
#
#
# def isPanValid(pan):
#     if len(pan) == 10:
#         Result = re.compile(r"[A-Za-z]{5}\d{4}[A-Za-z]{1}")
#         return Result.match(pan)
#     else:
#         return False
#
#
# # Aadhaar Card Validation
# def isAadhaarValid(aadhaar):
#     if len(aadhaar) == 12:
#         regex = r"^[0-9]{12}$"
#         return re.search(regex, aadhaar)
#     else:
#         return False
#
# # Aadhaar OTP Verify Api based on Digilocker
# def aadhaar_verify_otp(request_id, aadhaar_no,  otp):
#     try:
#         if not request_id or not aadhaar_no or not otp:
#             error = {
#                 "name": "Details Missing",
#                 "message": "Information Missing"
#             }
#             return error
#
#         request_data = {
#             "otp": str(otp),
#             "requestId": request_id,
#             "consent": "Y",
#             "aadhaarNo": aadhaar_no
#         }
#         payload = json.dumps(request_data)
#         url = settings.KARZA_API_URL + "/v3/aadhaar-xml/file"
#         headers = {
#             'x-karza-key': settings.KARZA_API_KEY
#         }
#         resp = requests.post(url=url, data=payload, headers=headers)
#         if resp.json().get("statusCode") == 101:
#             return resp.json()
#         raise Exception
#     except Exception as error:
#         error = {"name": "SERVER_ERROR", "message": str(error)}
#         return error
#
# # Aadhaar data download Api based on Digilocker
# def aadhaar_download(requestId):
#     try:
#         if requestId:
#             payload = {
#                 "requestId": requestId,
#                 "consent": "Y"
#             }
#             headers = {
#                 'x-karza-key': settings.KARZA_API_KEY
#             }
#             url = settings.KARZA_API_URL + "/v3/aadhaar/download"
#             resp = requests.post(url=url, data=json.dumps(payload), headers=headers)
#             if resp.json().get("statusCode") == 101:
#                 print(resp.json())
#                 return resp.json()
#         raise Exception
#     except Exception as error:
#         error = {"name": "SERVER_ERROR", "message": str(error)}
#         return error
#
#
# def verify_pan(pan):
#     try:
#         request_data = {
#             "pan": pan,
#             "getContactDetails": "Y",
#             "consent": "Y"
#         }
#         headers = {
#             "content-type": "application/json",
#             "x-karza-key": settings.KARZA_API_KEY,
#         }
#
#         url = settings.KARZA_API_URL + "/v3/pan-profile"
#         resp = requests.post(url=url, headers=headers, data=json.dumps(request_data))
#         if resp.json().get("statusCode") == 101:
#             return resp.json()
#         raise Exception("Something went wrong")
#     except Exception as error:
#         error = {"name": "SERVER_ERROR", "message": str(error)}
#         raise Exception(error)
#
#
# def send_aadhaar_otp(aadhaar):
#     try:
#         if not aadhaar:
#             error = {
#                 "name": "AADHAAR_MISSING",
#                 "message": "Aadhaar information missing",
#             }
#             return error
#         request_data = {
#             "consent": "Y",
#             "aadhaarNo": aadhaar
#         }
#         payload = json.dumps(request_data)
#         if not isAadhaarValid(aadhaar):
#             error = {
#                 "name": "INVALID_AADHAAR",
#                 "message": "Aadhaar number length incorrect"
#             }
#             return error
#
#         url = settings.KARZA_API_URL + "/v3/aadhaar-xml/otp"
#         headers = {
#             'x-karza-key': settings.KARZA_API_KEY
#         }
#         resp = requests.post(url=url, data=payload, headers=headers)
#         if resp.json().get("statusCode") == 101:
#             return resp.json()
#         raise Exception
#     except Exception as error:
#         error = {"name": "SERVER_ERROR", "message": str(error)}
#         return error
#
# class Decentro:
#     def verify_pan(self, pan):
#         try:
#             url = "https://in.staging.decentro.tech/kyc/public_registry/validate"
#
#             payload = json.dumps({
#                 "reference_id": "0000-0000-0000-2005",
#                 "document_type": "PAN",
#                 "id_number": pan,
#                 "consent": "Y",
#                 "consent_purpose": "For KYC purpose only"
#             })
#             headers = {
#                 'client_id': settings.DECENTRO_CLIENT_ID,
#                 'client_secret': settings.DECENTRO_CLIENT_SECRET,
#                 'module_secret': settings.DECENTRO_MODULE_SECRET,
#                 'Content-Type': 'application/json'
#             }
#
#             response = requests.request("POST", url, headers=headers, data=payload)
#
#             if response.status_code == 200:
#                 return response.json()
#             raise Exception("Something went wrong")
#         except Exception as error:
#             error = {"name": "SERVER_ERROR", "message": str(error)}
#             raise Exception(error)
#
#     def generate_aadhaar_otp(self, aadhaar):
#         try:
#
#             url = "https://in.staging.decentro.tech/v2/kyc/aadhaar/otp"
#             reference_id = uuid.uuid4()
#             payload = json.dumps({
#                 "reference_id": reference_id.hex,
#                 "consent": True,
#                 "purpose": "For KYC purpose only",
#                 "aadhaar_number": aadhaar
#             })
#             headers = {
#                 'client_id': settings.DECENTRO_CLIENT_ID,
#                 'client_secret': settings.DECENTRO_CLIENT_SECRET,
#                 'module_secret': settings.DECENTRO_MODULE_SECRET,
#                 'Content-Type': 'application/json'
#             }
#
#             response = requests.request("POST", url, headers=headers, data=payload)
#             if response.status_code == 200:
#                 data = response.json()
#                 data['reference_id'] = reference_id.hex
#                 return data
#             raise Exception("Something went wrong")
#         except Exception as error:
#             error = {"name": "SERVER_ERROR", "message": str(error)}
#             raise Exception(error)
#
#     def validate_aadhaar_otp(self, reference_id, otp, txn_id):
#         try:
#             url = "https://in.staging.decentro.tech/v2/kyc/aadhaar/otp/validate"
#
#             payload = json.dumps({
#                 "reference_id": reference_id,
#                 "consent": True,
#                 "purpose": "For KYC purpose only",
#                 "initiation_transaction_id": txn_id,
#                 "otp": otp,
#                 "share_code": "1111",
#                 "generate_pdf": True,
#                 "generate_xml": False
#             })
#             headers = {
#                 'client_id': settings.DECENTRO_CLIENT_ID,
#                 'client_secret': settings.DECENTRO_CLIENT_SECRET,
#                 'module_secret': settings.DECENTRO_MODULE_SECRET,
#                 'Content-Type': 'application/json'
#             }
#
#             response = requests.request("POST", url, headers=headers, data=payload)
#             if response.status_code == 200:
#                 return response.json()
#             raise Exception("Something went wrong")
#         except Exception as error:
#             error = {"name": "SERVER_ERROR", "message": str(error)}
#             raise Exception(error)
#
#
#
#
