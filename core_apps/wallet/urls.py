# wallet/urls.py

from django.urls import path
# Import directly from views.py (original file)
from .views import (
    CreateCustomerWalletAPIView, FinalizeRegistrationAPIView, TopUpStatusAPIView,
    UserWalletAPIView, WalletDetailsAPIView, WalletTransactionHistoryAPIView,
    TopUpMoneyAPIView, TopUpWebhookAPIView, WalletMovementCallbackAPIView,
    ManualRatificationWebhookAPIView
)
# Import from views/transaction.py (new file)
from .views.transaction import (
    WalletToWalletTransferAPIView,
    WalletToMpesaTransferAPIView,
    MpesaWithdrawalWebhookAPIView,
    TransactionHistoryAPIView, # General history
    ComprehensiveWalletHistoryAPIView, # Complete wallet history
    WalletTransactionSummaryAPIView, # Transaction summary and statistics
    GetWithdrawalFeeAPIView,
    # New contact-related views
    RecentContactsAPIView,
    CheckContactWalletAPIView,
    ContactTransactionHistoryAPIView # Contact-specific history
)
# Import from views/mpin.py
from .views.mpin import UpdateWalletMpinAPIView

# Import from views/beneficiary.py (bank beneficiary management)
from .views.beneficiary import (
    BankBeneficiaryListCreateAPIView,
    BankBeneficiaryDetailAPIView,
    RecentBankBeneficiariesAPIView,
    ActivateBankBeneficiaryAPIView
)

# Import from views/bank_transfer.py (bank transfers)
from .views.bank_transfer import (
    WalletToBankTransferAPIView,
    BankTransferWebhookAPIView,
    GetBankTransferFeeAPIView
)

urlpatterns = [
    path('finalize-registration/', FinalizeRegistrationAPIView.as_view(), name='finalize_registration'),
    path('create-wallet/', CreateCustomerWalletAPIView.as_view(), name='create-wallet'),
    path('', UserWalletAPIView.as_view(), name='user-wallet'),
    # Renamed for clarity
    path('top-up/transactions/', WalletTransactionHistoryAPIView.as_view(), name='wallet-transactions-all'),
    path('top-up/', TopUpMoneyAPIView.as_view(), name='top-up-money'),
    path('top-up/webhook/', TopUpWebhookAPIView.as_view(), name='top-up-webhook'),
    path('<str:wallet_id>/topups/<str:payment_id>/status/', TopUpStatusAPIView.as_view(), name='topup-status'),
    path('details/', WalletDetailsAPIView.as_view(), name='wallet-details'),

    # Wallet transfer endpoints
    path('transfers/wallet-to-wallet/', WalletToWalletTransferAPIView.as_view(), name='wallet-to-wallet-transfer'),
    path('transfers/wallet-to-mpesa/', WalletToMpesaTransferAPIView.as_view(), name='wallet-to-mpesa-transfer'),
    path('transfers/mpesa-webhook/', MpesaWithdrawalWebhookAPIView.as_view(), name='mpesa-withdrawal-webhook'),
    path('transfers/history/', TransactionHistoryAPIView.as_view(), name='transaction-history'), # Transfer transactions only
    path('transfers/withdrawal-fee/', GetWithdrawalFeeAPIView.as_view(), name='withdrawal-fee'),

    # Bank transfer endpoints
    path('transfers/wallet-to-bank/', WalletToBankTransferAPIView.as_view(), name='wallet-to-bank-transfer'),
    path('transfers/bank-webhook/', BankTransferWebhookAPIView.as_view(), name='bank-transfer-webhook'),
    path('transfers/bank-fee/', GetBankTransferFeeAPIView.as_view(), name='bank-transfer-fee'),

    # Complete wallet history endpoint
    path('history/', ComprehensiveWalletHistoryAPIView.as_view(), name='comprehensive-wallet-history'),
    path('history/summary/', WalletTransactionSummaryAPIView.as_view(), name='wallet-transaction-summary'),

    # Contact Management & History Endpoints
    path('contacts/recent/', RecentContactsAPIView.as_view(), name='recent-contacts'),
    path('contacts/check/', CheckContactWalletAPIView.as_view(), name='check-contact-wallet'),
    path('contacts/<int:contact_id>/history/', ContactTransactionHistoryAPIView.as_view(), name='contact-transaction-history'),

    # Bank Beneficiary Management Endpoints
    path('beneficiaries/', BankBeneficiaryListCreateAPIView.as_view(), name='bank-beneficiaries-list-create'),
    path('beneficiaries/<int:pk>/', BankBeneficiaryDetailAPIView.as_view(), name='bank-beneficiary-detail'),
    path('beneficiaries/recent/', RecentBankBeneficiariesAPIView.as_view(), name='recent-bank-beneficiaries'),
    path('beneficiaries/<int:pk>/activate/', ActivateBankBeneficiaryAPIView.as_view(), name='activate-bank-beneficiary'),

    # MPIN management endpoint
    path('mpin/update/', UpdateWalletMpinAPIView.as_view(), name='update-wallet-mpin'),
    
    # Webhook endpoints
    path('movement/callback/', WalletMovementCallbackAPIView.as_view(), name='wallet-movement-callback'),
    path('kyc/manual-ratification/webhook/', ManualRatificationWebhookAPIView.as_view(), name='manual-ratification-webhook'),
]
