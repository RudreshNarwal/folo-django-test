import logging
import uuid
import ipaddress
from django.db import transaction
from django.utils import timezone
from ..models import Transaction, TopUpTransaction, Wallet, WalletMovementCallback

logger = logging.getLogger(__name__)


class WebhookProcessor:
    """Handles DTB webhook processing logic"""
    
    def _validate_ip_address(self, ip_string):
        """Validate and return a valid IP address or None"""
        if not ip_string or ip_string.lower() in ['unknown', 'null', 'none', '']:
            return None
        
        try:
            # Try to validate as IP address
            ipaddress.ip_address(ip_string)
            return ip_string
        except (ipaddress.AddressValueError, ValueError):
            return None
    
    def process_wallet_movement(self, webhook_data):
        """
        Process wallet movement webhook and create callback record.
        Returns: (WalletMovementCallback, created: bool)
        """
        dtb_transaction_id = webhook_data.get('transactionId')
        
        if not dtb_transaction_id:
            raise ValueError("Missing transactionId in webhook data")
        
        # Check for duplicate processing
        existing_callback = WalletMovementCallback.objects.filter(
            dtb_transaction_id=dtb_transaction_id
        ).first()
        
        if existing_callback:
            logger.info(f"Webhook already processed: {dtb_transaction_id}")
            return existing_callback, False
        
        try:
            with transaction.atomic():
                # Extract webhook data
                callback_data = self._extract_webhook_data(webhook_data)
                
                # Find original transaction
                original_transaction = self._find_original_transaction(callback_data['external_unique_id'])
                
                # Create callback record
                callback = WalletMovementCallback.objects.create(
                    dtb_transaction_id=dtb_transaction_id,
                    transaction=original_transaction.get('transaction'),
                    topup_transaction=original_transaction.get('topup_transaction'),
                    webhook_data=webhook_data,
                    processed=True,
                    **callback_data
                )
                
                # Update original transaction if needed
                if original_transaction.get('transaction'):
                    self._update_transaction_status(original_transaction['transaction'], callback_data)
                elif original_transaction.get('topup_transaction'):
                    self._update_topup_status(original_transaction['topup_transaction'], callback_data)
                
                # Update wallet balance
                self._update_wallet_balance(callback_data['wallet_id'], callback_data['balance_after'])
                
                logger.info(f"Processed webhook: {dtb_transaction_id}")
                return callback, True
                
        except Exception as e:
            logger.error(f"Error processing webhook {dtb_transaction_id}: {e}")
            # Create failed callback record for audit
            try:
                safe_data = self._extract_webhook_data(webhook_data, safe=True)
                WalletMovementCallback.objects.create(
                    dtb_transaction_id=dtb_transaction_id,
                    webhook_data=webhook_data,
                    processed=False,
                    processing_error=str(e),
                    **safe_data
                )
            except Exception as audit_error:
                logger.error(f"Failed to create audit record for {dtb_transaction_id}: {audit_error}")
            raise
    
    def _extract_webhook_data(self, webhook_data, safe=False):
        """Extract and validate webhook data"""
        try:
            external_ref = webhook_data.get('externalUniqueId', '')
            
            # Strip DTB prefixes to get original UUID
            if external_ref.startswith(('DB-', 'CR-')):
                original_uuid_str = external_ref[3:]  # Remove prefix
            else:
                original_uuid_str = external_ref
            
            # Try to parse as UUID
            original_uuid = None
            if original_uuid_str:
                try:
                    original_uuid = uuid.UUID(original_uuid_str)
                except ValueError:
                    if not safe:
                        logger.warning(f"Invalid UUID format: {original_uuid_str}")
            
            return {
                'external_unique_id': original_uuid,
                'external_reference_id': external_ref,
                'wallet_id': webhook_data.get('walletId', 0),
                'transaction_type': webhook_data.get('type', ''),
                'amount': webhook_data.get('amount', 0),
                'currency': webhook_data.get('currency', 'KES'),
                'balance_after': webhook_data.get('balance', 0),
                'other_wallet_id': webhook_data.get('otherWalletId'),
                'location': self._validate_ip_address(webhook_data.get('location')),
            }
        except Exception as e:
            if safe:
                # Return minimal safe data for audit
                return {
                    'external_unique_id': None,
                    'external_reference_id': webhook_data.get('externalUniqueId', ''),
                    'wallet_id': webhook_data.get('walletId', 0),
                    'transaction_type': webhook_data.get('type', ''),
                    'amount': 0,
                    'currency': 'KES',
                    'balance_after': 0,
                    'other_wallet_id': None,
                    'location': None,
                }
            raise
    
    def _find_original_transaction(self, external_unique_id):
        """Find original transaction by external_unique_id"""
        if not external_unique_id:
            logger.warning("No external_unique_id provided for transaction matching")
            return {}
        
        # Try Transaction model first
        transaction = Transaction.objects.filter(
            external_unique_id=external_unique_id
        ).first()
        
        if transaction:
            logger.info(f"Found original transaction: {transaction.transaction_id}")
            return {'transaction': transaction}
        
        # Try TopUpTransaction model
        topup = TopUpTransaction.objects.filter(
            external_unique_id=external_unique_id
        ).first()
        
        if topup:
            logger.info(f"Found original topup transaction: {topup.payment_id}")
            return {'topup_transaction': topup}
        
        logger.warning(f"No original transaction found for: {external_unique_id}")
        return {}
    
    def _update_transaction_status(self, transaction, callback_data):
        """Update original transaction based on webhook data"""
        old_status = transaction.status
        
        # Update status if transaction was pending
        if transaction.status == 'PENDING':
            # For debit movements, mark as successful
            if callback_data['transaction_type'].startswith('tfr.debit'):
                transaction.status = 'SUCCESSFUL'
                transaction.save(update_fields=['status', 'updated_at'])
                logger.info(f"Updated transaction {transaction.transaction_id} from {old_status} to SUCCESSFUL")
            # For credit movements to the destination wallet, also mark as successful
            elif (callback_data['transaction_type'].startswith('tfr.credit') and 
                  transaction.transaction_type == 'WALLET_TO_WALLET' and
                  transaction.to_wallet and 
                  transaction.to_wallet.wallet_id == callback_data['wallet_id']):
                transaction.status = 'SUCCESSFUL'
                transaction.save(update_fields=['status', 'updated_at'])
                logger.info(f"Updated transaction {transaction.transaction_id} from {old_status} to SUCCESSFUL (credit received)")
    
    def _update_topup_status(self, topup_transaction, callback_data):
        """Update topup transaction based on webhook data"""
        old_status = topup_transaction.status
        
        # For credit movements (topups), mark as successful
        if (callback_data['transaction_type'].startswith('tfr.credit') and 
            topup_transaction.status == 'PENDING'):
            topup_transaction.status = 'SUCCESSFUL'
            topup_transaction.save(update_fields=['status'])
            logger.info(f"Updated topup {topup_transaction.payment_id} from {old_status} to SUCCESSFUL")
    
    def _update_wallet_balance(self, wallet_id, balance_after):
        """Update wallet balance from webhook"""
        try:
            wallet = Wallet.objects.get(wallet_id=wallet_id)
            old_balance = wallet.current_balance
            
            wallet.current_balance = balance_after
            wallet.available_balance = balance_after - float(wallet.reservations or 0)
            wallet.save(update_fields=['current_balance', 'available_balance', 'updated'])
            
            logger.info(f"Updated wallet {wallet_id} balance from {old_balance} to {balance_after}")
        except Wallet.DoesNotExist:
            logger.error(f"Wallet not found: {wallet_id}")
        except Exception as e:
            logger.error(f"Error updating wallet {wallet_id} balance: {e}")
