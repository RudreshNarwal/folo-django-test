import uuid
from django.core.validators import (
	MinValueValidator,
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
	provider_customer_id = models.IntegerField(null=True, blank=True)
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
	
	user = models.ForeignKey( User, on_delete=models.CASCADE, related_name='wallets')
	external_unique_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
	wallet_id = models.PositiveIntegerField(unique=True, help_text="A unique system-generated numeric identifier for the wallet. Possible values: >= 1.")
	wallet_type = models.ForeignKey(WalletType, on_delete=models.PROTECT, related_name='wallets')
	name = models.CharField(max_length=50, validators=[MinLengthValidator(3), MaxLengthValidator(50)], help_text="Name of the Wallet. Possible values: >= 3 characters and <= 50 characters.")
	description = models.CharField(max_length=200, blank=True, null=True, validators=[MaxLengthValidator(200)])
	card_type = models.CharField(max_length=20, choices=CardType.choices)
	status = models.CharField(max_length=20, choices=WalletStatus.choices, default=WalletStatus.ACTIVE)
	currency = models.CharField(max_length=3, default='KES',validators=[RegexValidator(regex=r'^[A-Z]{3}$', message="Currency must be a 3-letter ISO code.")])
	available_balance = models.DecimalField(max_digits=20, decimal_places=2, default=0.00, validators=[MinValueValidator(0)])
	current_balance = models.DecimalField(max_digits=20, decimal_places=2, default=0.00, validators=[MinValueValidator(0)], help_text="The balance in the wallet in the currency of the wallet")
	reservations = models.DecimalField(max_digits=20, decimal_places=2, default=0.00, help_text="The reservations placed on the wallet (uncommitted transactions).")
	account_number = models.CharField(max_length=50, unique=True),
	friendly_id = models.CharField(max_length=50, unique=True, blank=True, null=True, help_text="A unique reference for a wallet used for deposits and other transactions.")
	customer_id = models.BigIntegerField(blank=True, null=True)
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
