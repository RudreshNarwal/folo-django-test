import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import Transaction, TopUpTransaction
from .services.dtb_services import DTBService, DTBServiceError

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def check_transaction_timeout(self, transaction_id, transaction_type='wallet_transaction'):
    """
    Check transaction status and mark as EXPIRED if no webhook response received within timeout period.
    
    Args:
        transaction_id: UUID string of the transaction
        transaction_type: 'wallet_transaction' or 'topup_transaction'
    """
    try:
        if transaction_type == 'wallet_transaction':
            transaction = Transaction.objects.get(transaction_id=transaction_id)
            timeout_field = 'created_at'
        else:  # topup_transaction
            transaction = TopUpTransaction.objects.get(external_unique_id=transaction_id)
            timeout_field = 'created_at'
        
        # Check if transaction is still pending
        if transaction.status != 'PENDING':
            logger.info(f"Transaction {transaction_id} is no longer pending (status: {transaction.status}). Timeout check cancelled.")
            return f"Transaction {transaction_id} status: {transaction.status}"
        
        # Check if transaction has timed out (5 minutes)
        created_time = getattr(transaction, timeout_field)
        timeout_threshold = created_time + timedelta(minutes=5)
        current_time = timezone.now()
        
        if current_time >= timeout_threshold:
            # Try to refresh status from DTB one more time before marking as expired
            try:
                dtb_service = DTBService()
                status_updated = False
                
                if transaction_type == 'wallet_transaction':
                    if transaction.transaction_type == 'WALLET_TO_MPESA' and hasattr(transaction, 'withdrawal_id') and transaction.withdrawal_id:
                        # Check MPESA withdrawal status
                        try:
                            response = dtb_service.get_withdrawal_status(
                                transaction.from_wallet.wallet_id,
                                transaction.withdrawal_id
                            )
                            if isinstance(response, dict) and response.get('status'):
                                new_status = response.get('status')
                                if new_status != 'PENDING':
                                    transaction.status = 'SUCCESSFUL' if new_status == 'SUCCESSFUL' else 'FAILED'
                                    transaction.save()
                                    status_updated = True
                                    logger.info(f"Updated transaction {transaction_id} status from DTB: {new_status}")
                        except DTBServiceError as e:
                            logger.warning(f"Failed to check DTB status for transaction {transaction_id}: {e}")
                    
                    elif transaction.transaction_type in ['WALLET_TO_BANK', 'WALLET_TO_PESALINK'] and hasattr(transaction, 'withdrawal_id') and transaction.withdrawal_id:
                        # Check bank transfer status using withdrawal_id
                        try:
                            response = dtb_service.get_withdrawal_status(
                                transaction.from_wallet.wallet_id,
                                transaction.withdrawal_id
                            )
                            if isinstance(response, dict) and response.get('status'):
                                new_status = response.get('status')
                                if new_status != 'PENDING':
                                    transaction.status = 'SUCCESSFUL' if new_status == 'SUCCESSFUL' else 'FAILED'
                                    transaction.save()
                                    status_updated = True
                                    logger.info(f"Updated bank transfer {transaction_id} status from DTB: {new_status}")
                        except DTBServiceError as e:
                            logger.warning(f"Failed to check DTB status for bank transfer {transaction_id}: {e}")
                    
                    elif transaction.transaction_type == 'WALLET_TO_WALLET':
                        # For wallet-to-wallet transfers, refresh wallet balance to see if transaction was processed
                        try:
                            wallet_details = dtb_service.get_wallet_details(transaction.from_wallet.wallet_id)
                            # If balance changed significantly, transaction might have been processed
                            # This is a heuristic approach since wallet-to-wallet may not have specific status endpoints
                            logger.info(f"Checked wallet balance for wallet-to-wallet transaction {transaction_id}")
                            # For now, we'll still mark as expired if no webhook received
                        except DTBServiceError as e:
                            logger.warning(f"Failed to check wallet balance for wallet-to-wallet transaction {transaction_id}: {e}")
                
                else:  # topup_transaction
                    if hasattr(transaction, 'payment_id') and transaction.payment_id:
                        try:
                            response = dtb_service.get_top_up_status(
                                transaction.wallet.wallet_id,
                                transaction.payment_id
                            )
                            if isinstance(response, dict) and response.get('status'):
                                new_status = response.get('status')
                                if new_status != 'PENDING':
                                    transaction.status = new_status
                                    transaction.save()
                                    status_updated = True
                                    logger.info(f"Updated top-up transaction {transaction_id} status from DTB: {new_status}")
                        except DTBServiceError as e:
                            logger.warning(f"Failed to check DTB status for top-up transaction {transaction_id}: {e}")
                
                # If status was not updated from DTB, mark as expired
                if not status_updated:
                    old_status = transaction.status
                    transaction.status = 'EXPIRED'
                    
                    # Add timeout information to extra_info
                    if not transaction.extra_info:
                        transaction.extra_info = {}
                    transaction.extra_info['timeout_info'] = {
                        'expired_at': current_time.isoformat(),
                        'original_status': old_status,
                        'timeout_reason': 'No webhook response received within 5 minutes',
                        'last_dtb_check': current_time.isoformat()
                    }
                    
                    transaction.save()
                    logger.warning(f"Transaction {transaction_id} marked as EXPIRED due to timeout (no webhook response within 5 minutes)")
                    
                    return f"Transaction {transaction_id} marked as EXPIRED due to timeout"
                else:
                    return f"Transaction {transaction_id} status updated from DTB: {transaction.status}"
                    
            except DTBServiceError as e:
                logger.error(f"DTB service error while checking timeout for transaction {transaction_id}: {e}")
                # Still mark as expired even if DTB check failed
                transaction.status = 'EXPIRED'
                if not transaction.extra_info:
                    transaction.extra_info = {}
                transaction.extra_info['timeout_info'] = {
                    'expired_at': current_time.isoformat(),
                    'original_status': 'PENDING',
                    'timeout_reason': 'No webhook response within 5 minutes, DTB check failed',
                    'dtb_error': str(e)
                }
                transaction.save()
                logger.warning(f"Transaction {transaction_id} marked as EXPIRED due to timeout and DTB check failure")
                return f"Transaction {transaction_id} marked as EXPIRED (timeout + DTB error)"
        else:
            # Not timed out yet, schedule another check
            remaining_time = (timeout_threshold - current_time).total_seconds()
            logger.info(f"Transaction {transaction_id} not timed out yet. Remaining: {remaining_time:.0f} seconds")
            
            # Schedule next check in 1 minute or when timeout occurs, whichever is sooner
            next_check_delay = min(60, max(10, remaining_time))
            raise self.retry(countdown=int(next_check_delay))
            
    except (Transaction.DoesNotExist, TopUpTransaction.DoesNotExist):
        logger.error(f"Transaction {transaction_id} not found for timeout check")
        return f"Transaction {transaction_id} not found"
        
    except Exception as e:
        logger.error(f"Unexpected error during timeout check for transaction {transaction_id}: {e}")
        raise self.retry(exc=e)


@shared_task
def schedule_transaction_timeout_check(transaction_id, transaction_type='wallet_transaction', delay_minutes=5):
    """
    Schedule a timeout check for a transaction.
    
    Args:
        transaction_id: UUID string of the transaction
        transaction_type: 'wallet_transaction' or 'topup_transaction'
        delay_minutes: Minutes to wait before first timeout check (default: 5)
    """
    check_transaction_timeout.apply_async(
        args=[transaction_id, transaction_type],
        countdown=delay_minutes * 60
    )
    logger.info(f"Scheduled timeout check for {transaction_type} {transaction_id} in {delay_minutes} minutes")
    return f"Timeout check scheduled for {transaction_id}"


@shared_task
def cleanup_expired_transactions():
    """
    Periodic task to clean up old expired transactions and update wallet balances.
    This should be run via Celery Beat every hour.
    """
    try:
        # Find expired transactions older than 1 hour
        one_hour_ago = timezone.now() - timedelta(hours=1)
        
        # Handle regular Transaction model
        expired_transactions = Transaction.objects.filter(
            status='EXPIRED',
            updated_at__lt=one_hour_ago
        )
        
        # Handle TopUpTransaction model  
        expired_topup_transactions = TopUpTransaction.objects.filter(
            status='EXPIRED',
            created_at__lt=one_hour_ago  # TopUpTransaction uses created_at
        )
        
        count = 0
        
        # Clean up regular transactions
        for transaction in expired_transactions:
            if transaction.from_wallet:
                try:
                    dtb_service = DTBService()
                    wallet_details = dtb_service.get_wallet_details(transaction.from_wallet.wallet_id)
                    wallet = transaction.from_wallet
                    wallet.available_balance = wallet_details['availableBalance']
                    wallet.current_balance = wallet_details['currentBalance']
                    wallet.save()
                    count += 1
                    logger.info(f"Updated balance for wallet {wallet.wallet_id} after expired transaction cleanup")
                except DTBServiceError as e:
                    logger.error(f"Failed to update wallet balance for expired transaction {transaction.transaction_id}: {e}")
        
        # Clean up top-up transactions
        for topup_transaction in expired_topup_transactions:
            if topup_transaction.wallet:
                try:
                    dtb_service = DTBService()
                    wallet_details = dtb_service.get_wallet_details(topup_transaction.wallet.wallet_id)
                    wallet = topup_transaction.wallet
                    wallet.available_balance = wallet_details['availableBalance']
                    wallet.current_balance = wallet_details['currentBalance']
                    wallet.save()
                    count += 1
                    logger.info(f"Updated balance for wallet {wallet.wallet_id} after expired top-up cleanup")
                except DTBServiceError as e:
                    logger.error(f"Failed to update wallet balance for expired top-up transaction {topup_transaction.external_unique_id}: {e}")
        
        total_expired = len(expired_transactions) + len(expired_topup_transactions)
        logger.info(f"Cleaned up {total_expired} expired transactions ({len(expired_transactions)} regular, {len(expired_topup_transactions)} top-up) and updated {count} wallet balances")
        return f"Cleaned up {total_expired} expired transactions"
        
    except Exception as e:
        logger.error(f"Error during expired transaction cleanup: {e}")
        raise 