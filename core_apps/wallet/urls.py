# wallet/urls.py

from django.urls import path
from .views import CreateCustomerWalletAPIView, FinalizeRegistrationAPIView

urlpatterns = [
    path('finalize-registration/', FinalizeRegistrationAPIView.as_view(), name='finalize_registration'),
    path('create-wallet/', CreateCustomerWalletAPIView.as_view(), name='create-wallet'),
]
