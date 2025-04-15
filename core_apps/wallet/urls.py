# wallet/urls.py

from django.urls import path
# Import directly from views.py (original file)
from .views import CreateCustomerWalletAPIView, FinalizeRegistrationAPIView, TopUpStatusAPIView, UserWalletAPIView, \
    WalletDetailsAPIView, WalletTransactionHistoryAPIView, TopUpMoneyAPIView, TopUpWebhookAPIView
# Import from views/transaction.py (new file)
from .views.transaction import (
    WalletToWalletTransferAPIView, 
    WalletToMpesaTransferAPIView, 
    MpesaWithdrawalWebhookAPIView,
    TransactionHistoryAPIView,
    GetWithdrawalFeeAPIView
)
# Import from views/mpin.py
from .views.mpin import UpdateWalletMpinAPIView

urlpatterns = [
    path('finalize-registration/', FinalizeRegistrationAPIView.as_view(), name='finalize_registration'),
    path('create-wallet/', CreateCustomerWalletAPIView.as_view(), name='create-wallet'),
    path('', UserWalletAPIView.as_view(), name='user-wallet'),
    path('transactions/', WalletTransactionHistoryAPIView.as_view(), name='wallet-transactions'),
    path('top-up/', TopUpMoneyAPIView.as_view(), name='top-up-money'),
    path('top-up/webhook/', TopUpWebhookAPIView.as_view(), name='top-up-webhook'),
    path('<str:wallet_id>/topups/<str:payment_id>/status/', TopUpStatusAPIView.as_view(), name='topup-status'),
    path('details/', WalletDetailsAPIView.as_view(), name='wallet-details'),
    
    # New wallet transfer endpoints
    path('transfers/wallet-to-wallet/', WalletToWalletTransferAPIView.as_view(), name='wallet-to-wallet-transfer'),
    path('transfers/wallet-to-mpesa/', WalletToMpesaTransferAPIView.as_view(), name='wallet-to-mpesa-transfer'),
    path('transfers/mpesa-webhook/', MpesaWithdrawalWebhookAPIView.as_view(), name='mpesa-withdrawal-webhook'),
    path('transfers/history/', TransactionHistoryAPIView.as_view(), name='transaction-history'),
    path('transfers/withdrawal-fee/', GetWithdrawalFeeAPIView.as_view(), name='withdrawal-fee'),
    
    # MPIN management endpoint
    path('mpin/update/', UpdateWalletMpinAPIView.as_view(), name='update-wallet-mpin'),
]
