from django.contrib import admin
from .models import (
    CustomerProfile, ProviderDocument, WalletType, Wallet, 
    TopUpTransaction, UserContact, BankBeneficiary, 
    Transaction, WalletMovementCallback
)


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'customer_id', 'kyc_status', 'provider_name', 'created_at']
    list_filter = ['kyc_status', 'provider_name', 'created_at']
    search_fields = ['user__mobile', 'user__email', 'customer_id']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(WalletType)
class WalletTypeAdmin(admin.ModelAdmin):
    list_display = ['wallet_type_id', 'name', 'allowed']
    list_filter = ['allowed']
    search_fields = ['name']


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ['wallet_id', 'user', 'status', 'current_balance', 'available_balance', 'currency']
    list_filter = ['status', 'currency', 'card_type']
    search_fields = ['wallet_id', 'user__mobile', 'friendly_id', 'account_number']
    readonly_fields = ['created', 'updated', 'external_unique_id']
    raw_id_fields = ['user', 'customer', 'wallet_type']


@admin.register(TopUpTransaction)
class TopUpTransactionAdmin(admin.ModelAdmin):
    list_display = ['payment_id', 'status', 'amount', 'currency', 'wallet', 'created_at']
    list_filter = ['status', 'currency', 'payment_type', 'created_at']
    search_fields = ['payment_id', 'external_unique_id', 'gateway_transaction_id']
    readonly_fields = ['created_at', 'external_unique_id']
    raw_id_fields = ['wallet', 'customer']


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['transaction_id', 'transaction_type', 'status', 'amount', 'currency', 'user', 'created_at']
    list_filter = ['transaction_type', 'status', 'currency', 'created_at']
    search_fields = ['transaction_id', 'external_unique_id', 'external_reference_id', 'user__mobile']
    readonly_fields = ['transaction_id', 'created_at', 'updated_at']
    raw_id_fields = ['user', 'customer', 'from_wallet', 'to_wallet', 'contact', 'bank_beneficiary']


@admin.register(WalletMovementCallback)
class WalletMovementCallbackAdmin(admin.ModelAdmin):
    list_display = [
        'dtb_transaction_id', 
        'transaction_type', 
        'amount', 
        'wallet_id', 
        'processed', 
        'created_at'
    ]
    list_filter = [
        'transaction_type', 
        'processed', 
        'currency', 
        'created_at'
    ]
    search_fields = [
        'dtb_transaction_id', 
        'external_unique_id', 
        'external_reference_id',
        'wallet_id'
    ]
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['transaction', 'topup_transaction']
    
    fieldsets = (
        ('Identification', {
            'fields': ('dtb_transaction_id', 'external_unique_id', 'external_reference_id')
        }),
        ('Transaction Details', {
            'fields': ('transaction', 'topup_transaction', 'transaction_type', 'amount', 'currency')
        }),
        ('Wallet Information', {
            'fields': ('wallet_id', 'balance_after', 'other_wallet_id', 'location')
        }),
        ('Processing', {
            'fields': ('processed', 'processing_error')
        }),
        ('Audit', {
            'fields': ('webhook_data', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(UserContact)
class UserContactAdmin(admin.ModelAdmin):
    list_display = ['user', 'name', 'phone_number', 'last_used']
    list_filter = ['last_used', 'created_at']
    search_fields = ['user__mobile', 'name', 'phone_number']
    raw_id_fields = ['user']


@admin.register(BankBeneficiary)
class BankBeneficiaryAdmin(admin.ModelAdmin):
    list_display = ['user', 'account_holder_name', 'bank_name', 'account_number', 'is_active']
    list_filter = ['is_active', 'bank_name', 'created_at']
    search_fields = ['user__mobile', 'account_holder_name', 'account_number', 'bank_name']
    raw_id_fields = ['user']
