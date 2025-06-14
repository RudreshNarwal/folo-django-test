import uuid
from django.db import models
from django.conf import settings

from core_apps.international_wallet.models import Customer
from generics.utils.models import GenericModel

# It's a good practice to use the AUTH_USER_MODEL from settings
User = settings.AUTH_USER_MODEL


class InternationalWalletTransaction(GenericModel):
    """
    Represents an international wallet transaction, tracking its lifecycle,
    payment rails, and associated details.
    """

    # --- Enums for Choice Fields ---
    # Using TextChoices for better readability and organization.

    class PaymentRail(models.TextChoices):
        ACH = ('ACH', 'ACH')
        WIRE = ('WIRE', 'Wire')
        ACH_PUSH = ('ACH_PUSH', 'ACH Push')
        ACH_SAME_DAY = ('ACH_SAME_DAY', 'ACH Same Day')
        ARBITRUM = ('ARBITRUM', 'Arbitrum')
        AVALANCHE_C_CHAIN = ('AVALANCHE_C_CHAIN', 'Avalanche C-Chain')
        BASE = ('BASE', 'Base')
        BRIDGE_WALLET = ('BRIDGE_WALLET', 'Bridge Wallet')
        ETHEREUM = ('ETHEREUM', 'Ethereum')
        OPTIMISM = ('OPTIMISM', 'Optimism')
        POLYGON = ('POLYGON', 'Polygon')
        SEPA = ('SEPA', 'SEPA')
        SOLANA = ('SOLANA', 'Solana')
        SPEI = ('SPEI', 'SPEI')
        STELLAR = ('STELLAR', 'Stellar')
        SWIFT = ('SWIFT', 'SWIFT')
        TRON = ('TRON', 'Tron')

    class Currency(models.TextChoices):
        DAI = ('DAI', 'DAI')
        EUR = ('EUR', 'EUR')
        EURC = ('EURC', 'EURC')
        MXN = ('MXN', 'MXN')
        PYUSD = ('PYUSD', 'PYUSD')
        USDB = ('USDB', 'USDB')
        USD = ('USD', 'USD')
        USDC = ('USDC', 'USDC')
        USDT = ('USDT', 'USDT')

    class TransactionState(models.TextChoices):
        # Internal
        NOT_STARTED = ('NOT_STARTED', 'Not Started')
        FAILED = ('FAILED', 'Failed')
        # External
        AWAITING_FUNDS = ('AWAITING_FUNDS', 'Awaiting Funds')
        IN_REVIEW = ('IN_REVIEW', 'In Review')
        FUNDS_RECEIVED = ('FUNDS_RECEIVED', 'Funds Received')
        PAYMENT_SUBMITTED = ('PAYMENT_SUBMITTED', 'Payment Submitted')
        PAYMENT_PROCESSED = ('PAYMENT_PROCESSED', 'Payment Processed')
        CANCELED = ('CANCELED', 'Canceled')
        ERROR = ('ERROR', 'Error')
        UNDELIVERABLE = ('UNDELIVERABLE', 'Undeliverable')
        RETURNED = ('RETURNED', 'Returned')
        REFUNDED = ('REFUNDED', 'Refunded')

    # --- Model Fields ---
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='wallet_transactions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wallet_transactions')
    txn_date = models.DateTimeField(auto_now_add=True, help_text="The date and time when the transaction was created.")

    # --- Source Details ---
    amount = models.DecimalField(max_digits=19, decimal_places=4, help_text="The amount of the transaction.")
    final_amount = models.DecimalField(max_digits=19, decimal_places=4, blank=True, null=True, help_text="The amount of the final transaction.")
    exchange_fee = models.DecimalField(max_digits=19, decimal_places=4, blank=True, null=True, help_text="The amount of the exchange fee.")
    developer_fee = models.DecimalField(max_digits=19, decimal_places=4, blank=True, null=True, help_text="The amount of the developer fee.")
    gas_fee = models.DecimalField(max_digits=19, decimal_places=4, blank=True, null=True, help_text="The amount of the gas fee.")
    source_payment_rail = models.CharField(max_length=20, choices=PaymentRail.choices, default=PaymentRail.SWIFT)
    source_currency = models.CharField(max_length=10, choices=Currency.choices, default=Currency.USD)
    from_address = models.CharField(max_length=255, blank=True, null=True,
                                    help_text="Source address, e.g., bank account number or crypto wallet address.")

    # --- Destination Details ---
    destination_payment_rail = models.CharField(max_length=20, choices=PaymentRail.choices, default=PaymentRail.SWIFT)
    destination_currency = models.CharField(max_length=10, choices=Currency.choices, default=Currency.USD)
    to_address = models.CharField(max_length=255, blank=True, null=True,
                                  help_text="Destination address, e.g., bank account number or crypto wallet address.")

    # --- Identifiers and State ---
    external_account_id = models.CharField(max_length=100, blank=True, null=True, help_text="Identifier for the external account.")
    transaction_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    client_reference_id = models.CharField(max_length=255, blank=True, null=True)
    state = models.CharField(max_length=20, choices=TransactionState.choices, default=TransactionState.NOT_STARTED)

    # --- Timestamps and Metadata ---
    receipt_url = models.URLField(max_length=512, blank=True, null=True)
    succeeded_at = models.DateTimeField(blank=True, null=True, help_text="Timestamp when the transaction succeeded.")

    # --- Audit Fields ---
    webhook_response = models.JSONField(default=dict, blank=True, null=True, help_text="Response from the webhook after processing the transaction.")

    class Meta:
        ordering = ['-created_on']
        db_table = "international_wallet_transaction"
        verbose_name = "International Wallet Transaction"
        verbose_name_plural = "International Wallet Transactions"

    def __str__(self):
        return f"Transaction {self.id} for {self.customer.user.username} - {self.state}"

    def mark_as_funds_received(self):
        """Helper method to mark a transaction as succeeded."""
        from django.utils import timezone
        self.state = self.TransactionState.FUNDS_RECEIVED
        self.succeeded_at = timezone.now()
        self.save(update_fields=['state', 'succeeded_at', 'updated_on'])

    def mark_as_failed(self):
        """Helper method to mark a transaction as failed."""
        self.state = self.TransactionState.FAILED
        self.save(update_fields=['state', 'updated_on'])
