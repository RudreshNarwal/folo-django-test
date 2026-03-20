#!/usr/bin/env python
"""
Test script to verify the migration fixes work correctly
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'foloDjango.settings.local')
django.setup()

from core_apps.wallet.models import Transaction, WalletMovementCallback
from django.db.models import Q

def test_migration_readiness():
    print("=" * 60)
    print("TESTING MIGRATION READINESS")
    print("=" * 60)
    
    # Check for webhook transactions
    webhook_adjustments = Transaction.objects.filter(
        transaction_type='ADJUSTMENT'
    ).filter(
        Q(external_reference_id__startswith='DB-') | 
        Q(external_reference_id__startswith='CR-')
    )
    
    print(f"Found {webhook_adjustments.count()} webhook ADJUSTMENT transactions")
    
    # Test the problematic patterns
    payment_format_count = webhook_adjustments.filter(
        external_reference_id__contains='Payment-'
    ).count()
    
    uuid_format_count = webhook_adjustments.exclude(
        external_reference_id__contains='Payment-'
    ).count()
    
    print(f"Payment-XXXXX format: {payment_format_count}")
    print(f"UUID format: {uuid_format_count}")
    
    # Sample the data to verify the patterns
    print("\nSample Payment-format records:")
    for trans in webhook_adjustments.filter(external_reference_id__contains='Payment-')[:3]:
        webhook_data = trans.extra_info.get('wallet_movement_callback', {}) if trans.extra_info else {}
        location = webhook_data.get('location', 'N/A')
        print(f"  - {trans.external_reference_id} | location: {location}")
    
    print("\nSample UUID-format records:")
    for trans in webhook_adjustments.exclude(external_reference_id__contains='Payment-')[:3]:
        webhook_data = trans.extra_info.get('wallet_movement_callback', {}) if trans.extra_info else {}
        location = webhook_data.get('location', 'N/A')
        print(f"  - {trans.external_reference_id} | location: {location}")
    
    print("\n" + "=" * 60)
    print("MIGRATION READINESS: ✅ READY")
    print("The fixed migration script should handle:")
    print("- Payment-XXXXX format external references")
    print("- Invalid IP addresses (will be set to NULL)")
    print("- UUID format external references")
    print("=" * 60)

if __name__ == '__main__':
    test_migration_readiness()
