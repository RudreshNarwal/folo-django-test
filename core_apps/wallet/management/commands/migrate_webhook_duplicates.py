from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from core_apps.wallet.models import Transaction, WalletMovementCallback
import json
import uuid
import logging
import ipaddress

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Migrate existing webhook-generated ADJUSTMENT transactions to WalletMovementCallback records'
    
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
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be migrated without making changes',
        )
        parser.add_argument(
            '--delete-after-migration',
            action='store_true',
            help='Delete ADJUSTMENT transactions after successful migration',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of records to process in each batch (default: 100)',
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        delete_after = options['delete_after_migration']
        batch_size = options['batch_size']
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be made"))
        
        # Find all ADJUSTMENT transactions with webhook data that have DTB prefixes
        webhook_transactions = Transaction.objects.filter(
            transaction_type='ADJUSTMENT',
        ).filter(
            Q(external_reference_id__startswith='DB-') | 
            Q(external_reference_id__startswith='CR-')
        ).order_by('created_at')
        
        total_count = webhook_transactions.count()
        self.stdout.write(f"Found {total_count} webhook-generated ADJUSTMENT transactions to migrate")
        
        if total_count == 0:
            self.stdout.write(self.style.SUCCESS("No webhook duplicates found. Database is clean!"))
            return
        
        migrated_count = 0
        skipped_count = 0
        error_count = 0
        
        # Process in batches
        for i in range(0, total_count, batch_size):
            batch = webhook_transactions[i:i + batch_size]
            self.stdout.write(f"Processing batch {i//batch_size + 1} ({len(batch)} records)...")
            
            for webhook_trans in batch:
                try:
                    if dry_run:
                        self.stdout.write(f"Would migrate: {webhook_trans.transaction_id} - {webhook_trans.external_reference_id}")
                        migrated_count += 1
                        continue
                    
                    with transaction.atomic():
                        # Extract webhook data from extra_info
                        webhook_data = webhook_trans.extra_info or {}
                        callback_data = webhook_data.get('wallet_movement_callback', {})
                        
                        if not callback_data:
                            self.stdout.write(f"Skipping {webhook_trans.transaction_id} - no webhook data found")
                            skipped_count += 1
                            continue
                        
                        # Generate DTB transaction ID from the webhook data or create a unique one
                        dtb_transaction_id = str(callback_data.get('transaction_id', f"migrated-{webhook_trans.id}"))
                        
                        # Check if this webhook callback already exists
                        existing_callback = WalletMovementCallback.objects.filter(
                            dtb_transaction_id=dtb_transaction_id
                        ).first()
                        
                        if existing_callback:
                            self.stdout.write(f"Skipping {webhook_trans.transaction_id} - callback already exists")
                            skipped_count += 1
                            continue
                        
                        # Find original transaction by stripping DB-/CR- prefix
                        original_transaction = None
                        original_topup = None
                        original_uuid = None
                        external_ref = webhook_trans.external_reference_id
                        
                        if external_ref and external_ref.startswith(('DB-', 'CR-')):
                            original_id_str = external_ref[3:]  # Remove prefix
                            
                            # Handle different formats: UUID vs Payment-XXXXX
                            if original_id_str.startswith('Payment-'):
                                # Handle Payment-XXXXX format (topup transactions)
                                try:
                                    payment_id = int(original_id_str.replace('Payment-', ''))
                                    from core_apps.wallet.models import TopUpTransaction
                                    original_topup = TopUpTransaction.objects.filter(
                                        payment_id=payment_id
                                    ).first()
                                    if original_topup:
                                        original_uuid = original_topup.external_unique_id
                                except (ValueError, TypeError) as e:
                                    self.stdout.write(f"Invalid Payment ID format: {original_id_str} - {e}")
                            else:
                                # Handle UUID format
                                try:
                                    original_uuid = uuid.UUID(original_id_str)
                                    
                                    # Try to find in Transaction model first
                                    original_transaction = Transaction.objects.filter(
                                        external_unique_id=original_uuid,
                                        transaction_type__in=['WALLET_TO_WALLET', 'WALLET_TO_MPESA', 'WALLET_TO_BANK']
                                    ).first()
                                    
                                    if not original_transaction:
                                        # Try TopUpTransaction model
                                        from core_apps.wallet.models import TopUpTransaction
                                        original_topup = TopUpTransaction.objects.filter(
                                            external_unique_id=original_uuid
                                        ).first()
                                        
                                except ValueError:
                                    self.stdout.write(f"Invalid UUID format in external_reference_id: {external_ref}")
                        
                        # Create WalletMovementCallback record
                        callback = WalletMovementCallback.objects.create(
                            dtb_transaction_id=dtb_transaction_id,
                            transaction=original_transaction,
                            topup_transaction=original_topup,
                            external_unique_id=original_uuid if 'original_uuid' in locals() else None,
                            external_reference_id=webhook_trans.external_reference_id,
                            wallet_id=callback_data.get('other_wallet_id', 0),
                            transaction_type=callback_data.get('type', 'unknown'),
                            amount=webhook_trans.amount,
                            currency=webhook_trans.currency,
                            balance_after=callback_data.get('balance_after', 0),
                            other_wallet_id=callback_data.get('other_wallet_id'),
                            location=self._validate_ip_address(callback_data.get('location')),
                            webhook_data=callback_data,
                            processed=True,
                            created_at=webhook_trans.created_at,
                            updated_at=webhook_trans.updated_at,
                        )
                        
                        migrated_count += 1
                        
                        # Link the callback to the original transaction for reference
                        if original_transaction:
                            self.stdout.write(f"Migrated: {webhook_trans.transaction_id} -> Callback {callback.id} (linked to original: {original_transaction.transaction_id})")
                        elif original_topup:
                            self.stdout.write(f"Migrated: {webhook_trans.transaction_id} -> Callback {callback.id} (linked to topup: {original_topup.payment_id})")
                        else:
                            self.stdout.write(f"Migrated: {webhook_trans.transaction_id} -> Callback {callback.id} (no original found)")
                        
                        # Delete original ADJUSTMENT transaction if requested
                        if delete_after:
                            webhook_trans.delete()
                            self.stdout.write(f"Deleted original webhook transaction: {webhook_trans.transaction_id}")
                        
                except Exception as e:
                    error_count += 1
                    self.stdout.write(self.style.ERROR(f"Error migrating {webhook_trans.transaction_id}: {e}"))
                    logger.error(f"Error migrating webhook transaction {webhook_trans.transaction_id}: {e}")
        
        # Summary
        self.stdout.write("\n" + "="*50)
        self.stdout.write(self.style.SUCCESS(f"Migration Summary:"))
        self.stdout.write(f"Total found: {total_count}")
        self.stdout.write(f"Successfully migrated: {migrated_count}")
        self.stdout.write(f"Skipped: {skipped_count}")
        self.stdout.write(f"Errors: {error_count}")
        
        if dry_run:
            self.stdout.write(self.style.WARNING("\nThis was a DRY RUN. No actual changes were made."))
            self.stdout.write("To perform the actual migration, run without --dry-run flag")
        else:
            self.stdout.write(self.style.SUCCESS(f"\nSuccessfully migrated {migrated_count} webhook transactions!"))
            
            if not delete_after:
                self.stdout.write(self.style.WARNING("Original ADJUSTMENT transactions were kept for safety."))
                self.stdout.write("Run with --delete-after-migration flag to remove them after verification.")
