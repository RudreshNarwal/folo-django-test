import uuid
from django.core.validators import (
	MaxValueValidator, MinValueValidator,
	RegexValidator,
	MaxLengthValidator,
	MinLengthValidator
)
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django_countries.fields import CountryField
from generics.utils.models import GenericModel
from core_apps.users.models.user import Document
from django.core.exceptions import ValidationError
from core_apps.users.models import User

User = get_user_model()


class CustomerProfile(models.Model):
	STATUS_CHOICES = [
		('PENDING', 'Pending'),
		('APPROVED', 'Approved'),
		('FAILED', 'Failed'),
	]
	PROVIDER_CHOICES = [
		('DTB', 'DTB')
	]
	
	user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='customer_profile')
	provider_name = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default='DTB')
	customer_id = models.IntegerField(null=True, blank=True, unique=True)
	external_unique_id = models.UUIDField(null=True, blank=True)
	kyc_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
	kyc_failure_stage = models.CharField(max_length=100, null=True, blank=True)
	kyc_error_message = models.TextField(null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)
	
	def __str__(self):
		return f"Customer Profile {self.user.mobile}"


class ProviderDocument(models.Model):
	document = models.OneToOneField(Document, on_delete=models.CASCADE, related_name='provider_document')
	provider_document_id = models.IntegerField(null=True, blank=True)
	
	def __str__(self):
		return f"Provider Document ID {self.provider_document_id} for Document {self.document.id}"


class WalletType(models.Model):
	"""
	Represents the different types of wallets available.
	"""
	wallet_type_id = models.PositiveIntegerField(unique=True)
	name = models.CharField(max_length=255)
	description = models.TextField(blank=True, null=True)
	allowed = models.BooleanField(default=False)
	
	def __str__(self):
		return f"{self.name} (ID: {self.wallet_type_id})"
	
	class Meta:
		verbose_name = "Wallet Type"
		verbose_name_plural = "Wallet Types"


class WalletStatus(models.TextChoices):
	ACTIVE = "ACTIVE", "Active"
	INACTIVE = "INACTIVE", "Inactive"
	SUSPENDED = "SUSPENDED", "Suspended"
	CLOSED = "CLOSED", "Closed"
	LOCKED = "LOCKED", "Locked"
	CANCELED = "CANCELED", "Canceled"
	CANCELLED = "CANCELLED", "Cancelled"
	BARRED = "BARRED", "Barred"
	PENDING = "PENDING", "Pending"


class CardType(models.TextChoices):
	VIRTUAL = "virtual", "Virtual"
	PHYSICAL = "physical", "Physical"


class Wallet(GenericModel):
	user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet_profile')
	external_unique_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
	wallet_id = models.PositiveIntegerField(unique=True,
	                                        help_text="A unique system-generated numeric identifier for the wallet. Possible values: >= 1.")
	mpin = models.CharField(max_length=6, validators=[
		MinLengthValidator(4), 
		MaxLengthValidator(6),
		RegexValidator(regex=r'^\d+$', message="MPIN must contain only digits.")
	], null=True, blank=True, help_text="4-6 digit PIN for securing wallet transactions")
	wallet_type = models.ForeignKey(WalletType, on_delete=models.PROTECT, related_name='wallets')
	name = models.CharField(max_length=50, validators=[MinLengthValidator(3), MaxLengthValidator(50)],
	                        help_text="Name of the Wallet. Possible values: >= 3 characters and <= 50 characters.")
	description = models.CharField(max_length=200, blank=True, null=True, validators=[MaxLengthValidator(200)])
	card_type = models.CharField(max_length=20, choices=CardType.choices, default=CardType.VIRTUAL)
	status = models.CharField(max_length=20, choices=WalletStatus.choices, default=WalletStatus.ACTIVE)
	currency = models.CharField(max_length=3, default='KES',
	                            validators=[RegexValidator(regex=r'^[A-Z]{3}$', message="Currency must be a 3-letter ISO code.")])
	available_balance = models.DecimalField(max_digits=20, decimal_places=2, default=0.00, validators=[MinValueValidator(0)])
	current_balance = models.DecimalField(max_digits=20, decimal_places=2, default=0.00, validators=[MinValueValidator(0)],
	                                      help_text="The balance in the wallet in the currency of the wallet")
	reservations = models.DecimalField(max_digits=20, decimal_places=2, default=0.00,
	                                   help_text="The reservations placed on the wallet (uncommitted transactions).")
	account_number = models.CharField(max_length=50, unique=True, blank=True, null=True,
	                                  help_text="A unique account number for the wallet.")
	friendly_id = models.CharField(max_length=50, unique=True, blank=True, null=True,
	                               help_text="A unique reference for a wallet used for deposits and other transactions.")
	customer = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE, related_name='wallets')
	organisation_id = models.BigIntegerField(blank=True, null=True,
	                                         help_text=(
		                                         "The organisation who owns this wallet. "
		                                         "If not provided, then the wallet must be owned by a customer and hence customerId should be provided."
	                                         )
	                                         )
	created = models.DateTimeField(default=timezone.now)
	updated = models.DateTimeField(auto_now=True)
	configuration = models.JSONField(blank=True, null=True, help_text="Additional configuration settings for the wallet.")
	
	def __str__(self):
		return f"Wallet {self.friendly_id or self.wallet_id} for {self.user.get_full_name}"
	
	def clean(self):
		super().clean()
		if not self.customer_id and not self.organisation_id:
			raise ValidationError("Either customer_id or organisation_id must be provided.")
	
	class Meta:
		verbose_name = "Wallet"
		verbose_name_plural = "Wallets"
		ordering = ['-created']


class TopUpTransaction(models.Model):
	STATUS_CHOICES = [
		('PENDING', 'Pending'),
		('SUCCESSFUL', 'Successful'),
		('ERROR_PERM', 'Error Permanent'),
		('EXPIRED', 'Expired'),  # Added for timeout handling
	]
	
	payment_id = models.BigIntegerField(unique=True, help_text="Unique payment ID from DTB.")
	external_unique_id = models.UUIDField(unique=True, help_text="Unique ID generated for the transaction.")
	status = models.CharField(
		max_length=20,
		choices=STATUS_CHOICES,
		default='PENDING',
		help_text="Transaction status: PENDING, SUCCESSFUL, or ERROR_PERM."
	)
	amount = models.DecimalField(
		max_digits=20,
		decimal_places=2,
		validators=[MinValueValidator(10), MaxValueValidator(150000)],
		help_text="Transaction amount between 10 and 150,000."
	)
	currency = models.CharField(max_length=3, default='KES', help_text="Currency code, e.g., KES.")
	description = models.TextField(blank=True, null=True, help_text="Description of the transaction.")
	merchant_name = models.CharField(max_length=255, help_text="Name of the merchant.")
	payment_type = models.CharField(max_length=50, help_text="Payment type, e.g., EFT.")
	gateway_transaction_id = models.CharField(null=True, blank=True, max_length=50)
	gateway = models.CharField(null=True, blank=True, max_length=50)
	created_at = models.DateTimeField(help_text="Timestamp when the transaction was created.")
	extra_info = models.JSONField(blank=True, null=True, help_text="Additional info as a JSON object.")
	payment_instrument_info = models.JSONField(help_text="Details about the payment instrument.")
	fee = models.DecimalField(
		max_digits=20,
		decimal_places=2,
		default=0.00,
		help_text="Transaction fee."
	)
	wallet = models.ForeignKey(
		Wallet,
		on_delete=models.CASCADE,
		related_name='topup_transactions',
		help_text="Associated wallet."
	)
	customer = models.ForeignKey(
		CustomerProfile,
		on_delete=models.CASCADE,
		related_name='topup_transactions',
		help_text="Associated customer."
	)
	error_description = models.TextField(
		blank=True,
		null=True,
		help_text="Error description if status is ERROR_PERM."
	)
	payment_reference = models.CharField(
		max_length=100,
		blank=True,
		null=True,
		help_text="Payment reference from DTB."
	)
	
	def __str__(self):
		return f"TopUpTransaction {self.payment_id} - {self.status}"
	
	class Meta:
		verbose_name = "TopUp Transaction"
		verbose_name_plural = "TopUp Transactions"
		ordering = ['-created_at']


class UserContact(models.Model):
	"""Stores contacts associated with a user for quick transfers."""
	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='contacts')
	name = models.CharField(max_length=100, blank=True, null=True) # Name is optional
	phone_number = models.CharField(max_length=20) # Consider adding validation
	last_used = models.DateTimeField(default=timezone.now)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		unique_together = ('user', 'phone_number') # A user can only have one contact per phone number
		ordering = ['-last_used', 'name']

	def __str__(self):
		return f"{self.user.get_username()}'s contact: {self.name or self.phone_number}"


class BankBeneficiary(models.Model):
	"""Model to store bank beneficiary details for transfers."""
	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bank_beneficiaries')
	account_holder_name = models.CharField(max_length=100, help_text="Name of the account holder")
	account_number = models.CharField(max_length=50, help_text="Bank account number")
	bank_code = models.CharField(max_length=10, help_text="Bank code (e.g., 0068 for Equity)")
	branch_code = models.CharField(max_length=10, help_text="Branch code")
	bank_name = models.CharField(max_length=100, help_text="Name of the bank")
	branch_name = models.CharField(max_length=100, blank=True, null=True, help_text="Name of the branch")
	nickname = models.CharField(max_length=50, blank=True, null=True, help_text="User-friendly name for the beneficiary")
	is_active = models.BooleanField(default=True, help_text="Whether this beneficiary is active")
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)
	last_used = models.DateTimeField(null=True, blank=True, help_text="Last time this beneficiary was used")
	
	class Meta:
		verbose_name = "Bank Beneficiary"
		verbose_name_plural = "Bank Beneficiaries"
		ordering = ['-last_used', '-created_at']
		unique_together = ('user', 'account_number', 'bank_code')  # Prevent duplicate accounts
	
	def __str__(self):
		return f"{self.account_holder_name} - {self.account_number} ({self.bank_name})"
	
	def get_display_name(self):
		"""Get a user-friendly display name for the beneficiary."""
		return self.nickname or f"{self.account_holder_name} - {self.bank_name}"


class Transaction(models.Model):
	TRANSACTION_TYPES = [
		('WALLET_TO_WALLET', 'Wallet to Wallet Transfer'),
		('WALLET_TO_MPESA', 'Wallet to MPESA Transfer'),
		('WALLET_TO_BANK', 'Wallet to Bank Transfer'),  # Added for EFT transfers
		('WALLET_TO_PESALINK', 'Wallet to PesaLink Transfer'),  # Added for PesaLink transfers
		('REFUND', 'Refund Transaction'),  # Added for refunds
		('REVERSAL', 'Transaction Reversal'),  # Added for reversals
		('ADJUSTMENT', 'Administrative Adjustment'),  # Added for manual adjustments
		('FEE', 'Transaction Fee'),  # Added for standalone fee transactions
	]
	
	STATUS_CHOICES = [
		('PENDING', 'Pending'),
		('SUCCESSFUL', 'Successful'),
		('FAILED', 'Failed'),
		('EXPIRED', 'Expired'),  # Added for expired transactions
		('PARTIAL', 'Partially Completed'),  # Added for partial transactions
		('REVERSED', 'Reversed'),  # Added for reversed transactions
	]
	
	transaction_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
	external_unique_id = models.UUIDField(unique=True, help_text="Unique ID generated for the transaction.")
	external_reference_id = models.CharField(max_length=100, null=True, blank=True, help_text="External reference ID from provider")
	transaction_type = models.CharField(max_length=50, choices=TRANSACTION_TYPES)
	amount = models.DecimalField(
		max_digits=20, 
		decimal_places=2,
		validators=[MinValueValidator(1)],
		help_text="Transaction amount."
	)
	fee = models.DecimalField(max_digits=20, decimal_places=2, default=0.00, help_text="Transaction fee.")
	from_wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT, null=True, related_name='outgoing_transactions')
	to_wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT, null=True, blank=True, related_name='incoming_transactions')
	currency = models.CharField(max_length=3, default='KES')
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
	user = models.ForeignKey(User, on_delete=models.PROTECT, null=True, related_name='transactions')
	customer = models.ForeignKey(CustomerProfile, on_delete=models.PROTECT, null=True, related_name='transactions')
	description = models.TextField(blank=True, null=True)
	gateway = models.CharField(max_length=50, null=True, blank=True)
	gateway_transaction_id = models.CharField(max_length=50, null=True, blank=True)
	deliver_to_phone = models.CharField(max_length=20, blank=True, null=True) # Keep for direct MPESA, maybe rename?
	reference = models.CharField(max_length=100, null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)
	extra_info = models.JSONField(null=True, blank=True)
	webhook_response = models.JSONField(null=True, blank=True, help_text="Webhook response data for the transaction")
	withdrawal_id = models.PositiveIntegerField(null=True, blank=True, help_text="ID for MPESA withdrawals")
	contact = models.ForeignKey(UserContact, on_delete=models.PROTECT, null=True, blank=True, related_name='transactions')
	bank_beneficiary = models.ForeignKey(BankBeneficiary, on_delete=models.PROTECT, null=True, blank=True, related_name='transactions', help_text="Bank beneficiary for bank transfers")
	tracing_context = models.CharField(max_length=100, null=True, blank=True, help_text="Tracing context from provider for debugging")
	
	def __str__(self):
		return f"Transaction {self.transaction_id} ({self.transaction_type}) - {self.status}"
	
	class Meta:
		verbose_name = "Transaction"
		verbose_name_plural = "Transactions"
		ordering = ['-created_at']


class WalletMovementCallback(models.Model):
	"""
	Store DTB wallet movement webhook callbacks separately from user transactions.
	This prevents duplicate transaction records while maintaining complete audit trail.
	"""
	
	# Primary identification - DTB's unique transaction ID to prevent duplicate processing
	dtb_transaction_id = models.CharField(
		max_length=50, 
		unique=True, 
		help_text="DTB's unique transaction ID to prevent duplicate processing"
	)
	
	# Link to original transactions (only one will be populated)
	transaction = models.ForeignKey(
		'Transaction', 
		null=True, 
		blank=True, 
		on_delete=models.CASCADE, 
		related_name='webhook_callbacks'
	)
	topup_transaction = models.ForeignKey(
		'TopUpTransaction', 
		null=True, 
		blank=True,
		on_delete=models.CASCADE, 
		related_name='webhook_callbacks'
	)
	
	# Extracted webhook data
	external_unique_id = models.UUIDField(
		null=True, 
		blank=True,
		help_text="Original external unique ID (without DB-/CR- prefix)"
	)
	external_reference_id = models.CharField(
		max_length=100, 
		help_text="DTB prefixed reference (DB-/CR-xxxxx)"
	)
	wallet_id = models.PositiveIntegerField(help_text="Wallet ID from webhook")
	transaction_type = models.CharField(
		max_length=50, 
		help_text="DTB transaction type (tfr.debit, tfr.credit, etc.)"
	)
	amount = models.DecimalField(
		max_digits=20, 
		decimal_places=2, 
		help_text="Movement amount (negative for debit, positive for credit)"
	)
	currency = models.CharField(max_length=3, default='KES')
	balance_after = models.DecimalField(
		max_digits=20, 
		decimal_places=2, 
		help_text="Wallet balance after this movement"
	)
	
	# Additional webhook metadata
	other_wallet_id = models.PositiveIntegerField(null=True, blank=True)
	location = models.GenericIPAddressField(null=True, blank=True)
	
	# Complete audit trail
	webhook_data = models.JSONField(help_text="Complete webhook payload from DTB")
	
	# Processing status
	processed = models.BooleanField(default=False)
	processing_error = models.TextField(null=True, blank=True)
	
	# Timestamps
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)
	
	class Meta:
		verbose_name = "Wallet Movement Callback"
		verbose_name_plural = "Wallet Movement Callbacks"
		ordering = ['-created_at']
		indexes = [
			models.Index(fields=['external_unique_id']),
			models.Index(fields=['wallet_id']),
			models.Index(fields=['dtb_transaction_id']),
			models.Index(fields=['processed']),
		]
	
	def __str__(self):
		return f"Webhook {self.dtb_transaction_id} - {self.transaction_type} ({self.amount})"


class SCASession(GenericModel):
	"""Track SCA challenges and pending transactions"""

	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sca_sessions')
	transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='sca_sessions')
	intent_id = models.CharField(max_length=100, unique=True)
	sca_type = models.CharField(max_length=20, default='OTP')
	status = models.CharField(max_length=20, default='PENDING',
	                         choices=[('PENDING', 'Pending'), ('COMPLETED', 'Completed'), ('FAILED', 'Failed')])

	# Store original transfer parameters for retry
	transfer_type = models.CharField(max_length=30)  # WALLET_TO_WALLET, WALLET_TO_MPESA, etc.
	transfer_payload = models.JSONField()  # Original request payload

	expires_at = models.DateTimeField()

	class Meta:
		db_table = 'wallet_sca_session'
		indexes = [
			models.Index(fields=['intent_id']),
			models.Index(fields=['user', 'status']),
		]

	def __str__(self):
		return f"SCA Session {self.intent_id} for {self.user.mobile} - {self.status}"
