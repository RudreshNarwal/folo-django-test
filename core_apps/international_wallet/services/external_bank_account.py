# app/services.py

from django.core.exceptions import ValidationError, ImproperlyConfigured
from django.conf import settings
from core_apps.international_wallet.models.external_bank_account import ExternalBankAccount
from django.contrib.auth.models import User  # Or your custom user model
from cryptography.fernet import Fernet, InvalidToken


ENCRYPTION_KEY = getattr(settings, "FERNET_KEY", None)
if not ENCRYPTION_KEY:
    raise ImproperlyConfigured(
        "FERNET_KEY is not set in your Django settings.py file. "
        "You must set it to a 32-byte url-safe base64-encoded key. "
        "\n--- To generate a key, run this in a Python shell: ---\n"
        "from cryptography.fernet import Fernet\n"
        "key = Fernet.generate_key()\n"
        "print(f\"FERNET_KEY = {key.decode()!r}\")\n"
        "----------------------------------------------------------"
    )

try:
    fernet = Fernet(ENCRYPTION_KEY.encode())
except (ValueError, TypeError) as e:
    raise ImproperlyConfigured(
        f"The FERNET_KEY is invalid. It must be 32 url-safe base64-encoded bytes. Error: {e}"
    )


def encrypt_value(value: str) -> str:
    """Encrypts a string value."""
    if not value or not ENCRYPTION_KEY:
        return value
    return fernet.encrypt(value.encode()).decode()


def decrypt_value(encrypted_value: str) -> str:
    """Decrypts an encrypted string."""
    if not encrypted_value or not ENCRYPTION_KEY:
        return encrypted_value
    try:
        return fernet.decrypt(encrypted_value.encode()).decode()
    except (InvalidToken, TypeError):
        # Handle cases where the value might not be encrypted or is corrupted
        return "Error: Could not decrypt data."


class ExternalBankAccountService:
    """
    Service layer to handle business logic for ExternalBankAccount models.
    """

    def is_account_already_exists(self, user: User, data: dict, account_to_exclude_id: int = None):
        """
        Checks if a user already has a bank account with the given details.
        This check is performed on unencrypted data by fetching, decrypting, and comparing.

        Args:
            user: The user instance to check accounts for.
            data: A dictionary containing the new, unencrypted details to check.
                  Expected keys: 'account_number', 'routing_number', 'iban'.
            account_to_exclude_id: Optional. The ID of an account to exclude from the check.
                                     This is used during updates to avoid comparing an account to itself.

        Returns:
            Boolean: True/False on a duplicate account is found.
        """
        new_account_number = data.get('account_number')
        new_routing_number = data.get('routing_number')
        new_iban = data.get('iban')

        # Nothing to check if identifying info isn't present in the new data
        if not new_iban and not (new_account_number and new_routing_number):
            return False

        # Build the queryset
        existing_accounts = ExternalBankAccount.objects.filter(user=user)
        if account_to_exclude_id:
            existing_accounts = existing_accounts.exclude(pk=account_to_exclude_id)

        # Iterate and compare in memory
        for account in existing_accounts:
            # Scenario 1: Check for duplicate account number and routing number
            if new_account_number and new_routing_number:
                decrypted_account_num = decrypt_value(account.account_number_encrypted)
                decrypted_routing_num = decrypt_value(account.routing_number_encrypted)
                if decrypted_account_num == new_account_number and decrypted_routing_num == new_routing_number:
                    return True

            # Scenario 2: Check for duplicate IBAN
            if new_iban:
                decrypted_iban = decrypt_value(account.iban_encrypted)
                if decrypted_iban == new_iban:
                    return True
        return False

    def create_bank_account(self, user: User, data: dict) -> ExternalBankAccount:
        """
        Creates a new bank account for a user.

        Args:
            user: The user instance to associate the account with.
            data: A dictionary of bank account details.
                  Expected keys: 'account_owner_name', 'bank_name', 'account_name' (optional),
                                 'account_number', 'iban', 'swift_bic', 'routing_number', customer_id,
                                 currency, and account_type.

        Returns:
            The newly created ExternalBankAccount instance.

        Raises:
            ValidationError: If required fields are missing or data is invalid.
        """
        # --- Basic Validation ---
        required_fields = ['account_owner_name', 'bank_name']
        if not all(field in data for field in required_fields):
            raise ValidationError("Missing required fields: account_owner_name, bank_name.")

        # For international accounts, we expect at least an IBAN or an account/routing number pair.
        if not data.get('iban') and not (data.get('account_number') and data.get('routing_number')):
            raise ValidationError("Please provide either an IBAN or both an Account Number and Routing Number.")

        # --- Create Model Instance with Encrypted Data ---
        bank_account = ExternalBankAccount(
            user=user,
            customer_id=data.get('customer_id'),
            account_owner_name=data.get('account_owner_name'),
            bank_name=data.get('bank_name'),
            account_name=data.get('account_name'),
            currency=data.get('currency'),
            account_type=data.get('account_type'),
            # Encrypt sensitive fields before saving
            account_number_encrypted=encrypt_value(data.get('account_number')),
            iban_encrypted=encrypt_value(data.get('iban')),
            swift_bic_encrypted=encrypt_value(data.get('swift_bic')),
            routing_number_encrypted=encrypt_value(data.get('routing_number')),
        )
        bank_account.full_clean()  # Run Django's model validation
        bank_account.save()

        return bank_account

    def update_bank_account(self, external_account_id: int, user: User, data: dict) -> ExternalBankAccount:
        """
        Updates an existing bank account.

        Args:
            external_account_id: The ID of the ExternalBankAccount to update.
            user: The user who owns the account (for permission checking).
            data: A dictionary with the fields to update.

        Returns:
            The updated ExternalBankAccount instance.

        Raises:
            ExternalBankAccount.DoesNotExist: If the account is not found.
            PermissionError: If the user does not own the account.
            ValidationError: If the update data is invalid.
        """
        external_account = ExternalBankAccount.objects.get(pk=external_account_id)

        if external_account.user != user:
            raise PermissionError("User does not have permission to update this account.")

        # --- Update Fields ---
        # Update non-sensitive fields directly
        for field in ['account_owner_name', 'bank_name', 'account_name']:
            if field in data:
                setattr(external_account, field, data[field])

        # Update sensitive fields with encryption
        if 'account_number' in data:
            external_account.account_number_encrypted = encrypt_value(data['account_number'])
        if 'iban' in data:
            external_account.iban_encrypted = encrypt_value(data['iban'])
        if 'swift_bic' in data:
            external_account.swift_bic_encrypted = encrypt_value(data['swift_bic'])
        if 'routing_number' in data:
            external_account.routing_number_encrypted = encrypt_value(data['routing_number'])

        external_account.full_clean()
        external_account.save()

        return external_account

    def get_decrypted_account_details(self, external_account_id: int, user: User) -> dict:
        """
        Retrieves a bank account and returns its details with sensitive
        information decrypted.

        Returns:
            A dictionary of the account details.
        """
        external_account = ExternalBankAccount.objects.get(pk=external_account_id)
        if external_account.user != user:
            raise PermissionError("User does not have permission to view this account.")

        return {
            "id": external_account.id,
            "account_owner_name": external_account.account_owner_name,
            "bank_name": external_account.bank_name,
            "account_name": external_account.account_name,
            "account_number": decrypt_value(external_account.account_number_encrypted),
            "iban": decrypt_value(external_account.iban_encrypted),
            "swift_bic": decrypt_value(external_account.swift_bic_encrypted),
            "routing_number": decrypt_value(external_account.routing_number_encrypted),
            "created_at": external_account.created_on,
        }
