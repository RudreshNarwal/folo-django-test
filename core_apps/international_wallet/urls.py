# wallet/urls.py
from django.urls import path
# Import the API views for the international wallet
from core_apps.international_wallet.views.bridge import (
    RequestTOSLinkAPI, CreateCustomerAPI, ExternalAccountAPI, InitiateTransferAPI
)


urlpatterns = [
    path('request-tos-link/', RequestTOSLinkAPI.as_view(), name='request_tos_link_api'),
    path('create-customer/', CreateCustomerAPI.as_view(), name='create_customer_api'),
    path('external-account/', ExternalAccountAPI.as_view(), name='external_account_api'),
    path('initiate-transfer/', InitiateTransferAPI.as_view(), name='initiate_transfer_api'),
]
