#!/usr/bin/env python
"""
Simple script to check the current status of webhook duplicate transactions
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'foloDjango.settings.local')
django.setup()

from core_apps.wallet.models import Transaction, WalletMovementCallback
from django.db.models import Q

def main():
    print("=" * 60)
    print("WEBHOOK DUPLICATE TRANSACTION STATUS CHECK")
    print("=" * 60)
    
    # Check for existing webhook-generated ADJUSTMENT transactions
    webhook_adjustments = Transaction.objects.filter(
        transaction_type='ADJUSTMENT'
    ).filter(
        Q(external_reference_id__startswith='DB-') | 
        Q(external_reference_id__startswith='CR-')
    )
    
    print(f"Current webhook-generated ADJUSTMENT transactions: {webhook_adjustments.count()}")
    
    # Check if we have any WalletMovementCallback records
    callbacks = WalletMovementCallback.objects.all()
    print(f"Current WalletMovementCallback records: {callbacks.count()}")
    
    # Sample data
    if webhook_adjustments.exists():
        print("\nSample webhook ADJUSTMENT transactions:")
        for trans in webhook_adjustments[:5]:
            print(f"  - {trans.transaction_id} | {trans.external_reference_id} | {trans.amount} {trans.currency}")
    
    if callbacks.exists():
        print("\nSample WalletMovementCallback records:")
        for callback in callbacks[:5]:
            print(f"  - {callback.dtb_transaction_id} | {callback.transaction_type} | {callback.amount} {callback.currency}")
    
    print("\n" + "=" * 60)
    print("NEXT STEPS:")
    if webhook_adjustments.exists():
        print("1. Run: python manage.py migrate_webhook_duplicates --dry-run")
        print("2. Review the output")
        print("3. Run: python manage.py migrate_webhook_duplicates")
        print("4. Optionally: python manage.py migrate_webhook_duplicates --delete-after-migration")
    else:
        print("✅ No webhook duplicates found! Database is clean.")
    print("=" * 60)

if __name__ == '__main__':
    main()
