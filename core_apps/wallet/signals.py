import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CustomerProfile
from .services.wallet_service import create_wallet_for_customer, WalletCreationError

logger = logging.getLogger(__name__)

@receiver(post_save, sender=CustomerProfile)
def auto_create_wallet_on_kyc_approval(sender, instance, created, **kwargs):
    """
    A signal that automatically creates a wallet when a customer's KYC is approved.
    
    This receiver is triggered whenever a CustomerProfile instance is saved.
    It checks if the `kyc_status` is 'APPROVED' and if the customer does not
    already have an active wallet.
    """
    # Check if the kyc_status is APPROVED
    if instance.kyc_status == 'APPROVED':
        try:
            # The create_wallet_for_customer service already checks if a wallet exists.
            logger.info(f"KYC approved for customer {instance.customer_id}. Attempting to create wallet.")
            create_wallet_for_customer(instance)
        except WalletCreationError as e:
            # Log the error. Admin should be notified about this failure.
            logger.error(f"Automatic wallet creation failed for customer {instance.customer_id}: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during automatic wallet creation for customer {instance.customer_id}: {e}")
    else:
        logger.info(f"Customer profile saved for user {instance.user.id} with status {instance.kyc_status}. No wallet created.") 