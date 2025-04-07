# wallet/urls.py

from django.urls import path
from .views import CreateCustomerWalletAPIView, FinalizeRegistrationAPIView, TopUpStatusAPIView, UserWalletAPIView, \
    WalletDetailsAPIView, WalletTransactionHistoryAPIView, TopUpMoneyAPIView, TopUpWebhookAPIView

urlpatterns = [
    path('finalize-registration/', FinalizeRegistrationAPIView.as_view(), name='finalize_registration'),
    path('create-wallet/', CreateCustomerWalletAPIView.as_view(), name='create-wallet'),
    path('', UserWalletAPIView.as_view(), name='user-wallet'),
    path('transactions/', WalletTransactionHistoryAPIView.as_view(), name='wallet-transactions'),
    path('top-up/', TopUpMoneyAPIView.as_view(), name='top-up-money'),
    path('top-up/webhook/', TopUpWebhookAPIView.as_view(), name='top-up-webhook'),
    path('<str:wallet_id>/topups/<str:payment_id>/status/', TopUpStatusAPIView.as_view(), name='topup-status'),
    path('details/', WalletDetailsAPIView.as_view(), name='wallet-details'),

]
