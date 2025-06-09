import logging
import uuid

from django.conf import settings
from django.core.mail import send_mail

from ..models import Wallet, WalletType, CustomerProfile
from .dtb_services import DTBService, DTBServiceAuthenticationError, DTBServiceAPIError, DTBServiceError

logger = logging.getLogger(__name__)

class WalletCreationError(Exception):
    """Custom exception for wallet creation failures."""
    pass

def create_wallet_for_customer(customer_profile: CustomerProfile):
    """
    Creates a wallet for a customer profile, handling all interactions with the DTB service.
    
    Args:
        customer_profile: The CustomerProfile instance for which to create a wallet.

    Returns:
        The created Wallet instance.

    Raises:
        WalletCreationError: If the wallet creation fails for any reason.
    """
    user = customer_profile.user
    
    # 1. Pre-condition checks
    if customer_profile.kyc_status != 'APPROVED':
        raise WalletCreationError("KYC not approved. Cannot create wallet.")
    
    if not customer_profile.customer_id:
        raise WalletCreationError("Customer is not registered with DTB.")

    if Wallet.objects.filter(user=user, status='ACTIVE').exists():
        logger.info(f"User {user.id} already has an active wallet. Skipping creation.")
        return Wallet.objects.get(user=user, status='ACTIVE')

    # 2. Initialize DTB Service
    dtb_service = DTBService()

    try:
        # 3. Fetch Allowed Wallet Types from DTB
        logger.info(f"Fetching allowed wallet types for customer {customer_profile.customer_id}")
        wallet_types_response = dtb_service.get_wallet_types()
        
        # Hardcoding walletTypeId 2497 as per previous logic.
        # This can be made dynamic if needed.
        selected_wallet_type_id = 2497
        
        if not selected_wallet_type_id:
            error_message = "No allowed wallet type found for the customer."
            raise WalletCreationError(error_message)

        # 4. Prepare Wallet Creation Payload
        wallet_payload = {
            "externalUniqueId": str(uuid.uuid4()),
            "status": "ACTIVE",
            "name": f"{user.first_name}'s Wallet",
            "description": "Folo Money Customer Wallet",
            "walletTypeId": selected_wallet_type_id,
            "cardType": "virtual",
            "configuration": []
        }

        # 5. Create Wallet via DTB API
        logger.info(f"Creating wallet on DTB for customer {customer_profile.customer_id}")
        wallet_response = dtb_service.create_wallet(customer_profile.customer_id, wallet_payload)

        # 6. Get or Create Local WalletType
        wallet_type_id = wallet_response.get('walletTypeId')
        wallet_type, _ = WalletType.objects.get_or_create(
            wallet_type_id=wallet_type_id,
            defaults={'name': f"Type {wallet_type_id}", 'allowed': True}
        )
        
        # 7. Create or Update Local Wallet Record
        wallet, created = Wallet.objects.update_or_create(
            wallet_id=wallet_response.get('walletId'),
            defaults={
                'user': user,
                'external_unique_id': uuid.UUID(wallet_response.get('externalUniqueId')),
                'wallet_type': wallet_type,
                'name': wallet_response.get('name'),
                'description': wallet_response.get('description'),
                'card_type': wallet_response.get('cardType', 'virtual'),
                'status': wallet_response.get('status'),
                'currency': wallet_response.get('currency', 'KES'),
                'available_balance': wallet_response.get('availableBalance', 0),
                'current_balance': wallet_response.get('currentBalance', 0),
                'reservations': wallet_response.get('reservations', 0),
                'account_number': wallet_response.get('accountNumber'),
                'friendly_id': wallet_response.get('friendlyId'),
                'customer': customer_profile,
                'organisation_id': wallet_response.get('organisationId'),
                'configuration': wallet_response.get('configuration')
            }
        )
        
        action = "created" if created else "updated"
        logger.info(f"Successfully {action} local wallet {wallet.wallet_id} for user {user.id}")

        # 8. Ensure customer profile status is marked as APPROVED.
        if customer_profile.kyc_status != 'APPROVED':
            customer_profile.kyc_status = 'APPROVED'
            customer_profile.save(update_fields=['kyc_status'])
            logger.info(f"Updated customer profile {customer_profile.id} status to APPROVED.")

        return wallet

    except (DTBServiceError, DTBServiceAPIError, DTBServiceAuthenticationError) as e:
        logger.error(f"DTB Service error during wallet creation for customer {customer_profile.customer_id}: {e}")
        raise WalletCreationError(f"DTB Service Error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during wallet creation for customer {customer_profile.customer_id}: {e}")
        raise WalletCreationError(f"An unexpected error occurred: {e}") 