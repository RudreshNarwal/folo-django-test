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
	customer_id = models.IntegerField(null=True, blank=True)
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


class Transaction(models.Model):
	TRANSACTION_TYPES = [
		('WALLET_TO_WALLET', 'Wallet to Wallet Transfer'),
		('WALLET_TO_MPESA', 'Wallet to MPESA Transfer')
	]
	
	STATUS_CHOICES = [
		('PENDING', 'Pending'),
		('SUCCESSFUL', 'Successful'),
		('FAILED', 'Failed'),
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
	
	def __str__(self):
		return f"Transaction {self.transaction_id} ({self.transaction_type}) - {self.status}"
	
	class Meta:
		verbose_name = "Transaction"
		verbose_name_plural = "Transactions"
		ordering = ['-created_at']
