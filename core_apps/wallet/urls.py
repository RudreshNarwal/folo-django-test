# wallet/urls.py

from django.urls import path
from .views import FinalizeRegistrationAPIView

urlpatterns = [
    path('finalize-registration/', FinalizeRegistrationAPIView.as_view(), name='finalize_registration'),
]
