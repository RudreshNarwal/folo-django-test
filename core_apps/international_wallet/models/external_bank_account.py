# app/models.py

from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from core_apps.international_wallet.models.customer import Customer

from generics.utils.models import GenericModel


class ExternalBankAccount(GenericModel):
    """
    Stores external bank account details for a user.
    This model is designed to accommodate international bank accounts by including
    fields for IBAN and SWIFT/BIC codes.

    **Security Note**:
    Sensitive fields like account_number, iban, and swift_bic are stored as
    encrypted text fields. The raw, unencrypted values should never be stored
    directly in the database. The service layer is responsible for encryption
    and decryption.
    """
    class CurrencyType(models.TextChoices):
        NA = ("N/A", _("N/A"))
        USD = ("USD", _("USD"))
        EUR = ("EUR", _("EUR"))
        MXN = ("MXN", _("MXN"))

    class AccountType(models.TextChoices):
        UNKNOWN = ("Unknown", _("Unknown"))
        US = ("US", _("US"))
        IBAN = ("Iban", _("Iban"))
        CLABE = ("Clabe", _("Clabe"))

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bank_accounts',
        verbose_name=_("User")
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='bank_accounts',
        verbose_name=_("Customer")
    )
    account_owner_name = models.CharField(
        _("Account Owner Name"),
        max_length=255,
        help_text=_("Full name of the person who owns the account.")
    )
    bank_name = models.CharField(
        _("Bank Name"),
        max_length=255,
        help_text=_("The name of the financial institution.")
    )
    # Optional name for the account (e.g., 'Primary Checking', 'Holiday Savings')
    account_name = models.CharField(
        _("Account Nickname"),
        max_length=100,
        blank=True,
        null=True,
        help_text=_("An optional, user-defined name for the account.")
    )

    # --- Sensitive Fields (Stored Encrypted) ---
    # We use TextField to ensure there's enough space for the encrypted string.
    account_number_encrypted = models.TextField(
        _("Encrypted Account Number"),
        help_text=_("Encrypted local bank account number.")
    )
    iban_encrypted = models.TextField(
        _("Encrypted IBAN"),
        blank=True,
        null=True,
        help_text=_("Encrypted International Bank Account Number (IBAN) for international transfers.")
    )
    swift_bic_encrypted = models.TextField(
        _("Encrypted SWIFT/BIC"),
        blank=True,
        null=True,
        help_text=_("Encrypted Bank Identifier Code (SWIFT/BIC) for international transfers.")
    )
    # Routing number can vary by country (e.g., ABA in US, Sort Code in UK)
    routing_number_encrypted = models.TextField(
        _("Encrypted Routing Number"),
        help_text=_("Encrypted routing, sort code, or other country-specific bank code.")
    )
    # Specific to bridge accounts
    currency = models.CharField(
        verbose_name=_("currency"),
        choices=CurrencyType.choices,
        max_length=128,
        default=CurrencyType.NA,
        null=True, blank=True,
    )
    # Specific to bridge accounts
    account_type = models.CharField(
        verbose_name=_("provider"),
        choices=AccountType.choices,
        max_length=128,
        default=AccountType.UNKNOWN,
        null=True, blank=True,
    )

    class Meta:
        db_table = "external_bank_account"
        verbose_name = _("External Bank Account")
        verbose_name_plural = _("External Bank Accounts")

    def __str__(self):
        return f"{self.user}'s {self.bank_name} Account"

    def get_display_name(self):
        """Returns the account nickname or a default masked number."""
        if self.account_name:
            return self.account_name
        return f"Bank Account ({self.id})"
