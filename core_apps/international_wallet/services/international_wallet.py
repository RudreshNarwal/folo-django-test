from django.utils import timezone
from typing import Any, Optional
from django.db import transaction
from django.contrib.auth import get_user_model
from core_apps.international_wallet.models.internationl_wallet import InternationalWalletTransaction

# Get the User model configured in settings.py
User = get_user_model()


class InternationalWalletTransactionService:
    """
    A service class to encapsulate the business logic for creating and
    updating InternationalWalletTransaction.
    """

    @staticmethod
    def create_transaction(user: User, **data: Any) -> Optional[InternationalWalletTransaction]:
        """
        Creates a new international wallet transaction.

        Args:
            user: The User instance initiating the transaction.
            **data: A dictionary containing the necessary transaction data,
                    such as amount, currency, addresses, etc.

        Returns:
            The newly created InternationalWalletTransaction instance, or None if creation fails.
        """
        try:
            # Use a database transaction to ensure atomicity. If any part fails, the entire operation is rolled back.
            with transaction.atomic():
                # For example, ensure required fields are present
                required_fields = [
                    'amount', 'source_payment_rail', 'source_currency', 'from_address',
                    'destination_payment_rail', 'destination_currency', 'external_account_id'
                ]
                for field in required_fields:
                    if field not in data:
                        # In a real app, you might raise a specific exception here.
                        print(f"Error: Missing required field '{field}'")
                        return None

                wallet_transaction = InternationalWalletTransaction.objects.create(
                    user=user,
                    **data
                )

                if data.get('state') == "funds_received":
                    # If we just updated the state to fund received, ensure succeeded_at is set.
                    wallet_transaction.mark_as_funds_received()

                return wallet_transaction
        except Exception as e:
            # It's good practice to log the exception
            print(f"Error creating transaction: {e}")
            return None

    @staticmethod
    def update_transaction(transaction_id: str, **data: Any) -> Optional[InternationalWalletTransaction]:
        """
        Updates an existing international wallet transaction.

        Args:
            transaction_id: The unique transaction_id of the wallet record to update.
            **data: A dictionary containing the fields to update.

        Returns:
            The updated InternationalWalletTransaction instance, or None if the transaction
            is not found or an error occurs.
        """
        try:
            with transaction.atomic():
                # Using select_for_update() locks the row to prevent race conditions
                # during the update process.
                transaction_obj = InternationalWalletTransaction.objects.select_for_update().get(
                    transaction_id=transaction_id
                )

                # Update the object's attributes from the data dictionary
                for key, value in data.items():
                    # Ensure we don't try to update fields that don't exist
                    if hasattr(transaction_obj, key):
                        setattr(transaction_obj, key, value)
                        print(key, value)
                        if key == "state" and value == "FUNDS_RECEIVED":
                            # If we are updating the state to funds received, set succeeded_at
                            setattr(transaction_obj, "succeeded_at", timezone.now())

                transaction_obj.save()

                return transaction_obj
        except InternationalWalletTransaction.DoesNotExist:
            print(f"Error: Transaction with ID '{transaction_id}' not found.")
            return None
        except Exception as e:
            print(f"Error updating transaction '{transaction_id}': {e}")
            return None

