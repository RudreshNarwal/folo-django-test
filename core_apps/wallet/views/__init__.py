# wallet views init
from .core import (
    FinalizeRegistrationAPIView,
    CreateCustomerWalletAPIView,
    TopUpStatusAPIView,
    UserWalletAPIView,
    WalletDetailsAPIView,
    WalletTransactionHistoryAPIView,
    TopUpMoneyAPIView,
    TopUpWebhookAPIView,
    WalletMovementCallbackAPIView,
    ManualRatificationWebhookAPIView
)

from .transaction import (
    WalletToWalletTransferAPIView,
    WalletToMpesaTransferAPIView,
    MpesaWithdrawalWebhookAPIView,
    TransactionHistoryAPIView,
    ComprehensiveWalletHistoryAPIView,
    WalletTransactionSummaryAPIView,
    GetWithdrawalFeeAPIView,
    RecentContactsAPIView,
    CheckContactWalletAPIView,
    ContactTransactionHistoryAPIView
)

from .mpin import (
    UpdateWalletMpinAPIView
)

from .beneficiary import (
    BankBeneficiaryListCreateAPIView,
    BankBeneficiaryDetailAPIView,
    RecentBankBeneficiariesAPIView,
    ActivateBankBeneficiaryAPIView
)

from .bank_transfer import (
    WalletToBankTransferAPIView,
    BankTransferWebhookAPIView,
    GetBankTransferFeeAPIView
)
