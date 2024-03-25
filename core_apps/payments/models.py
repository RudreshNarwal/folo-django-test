import uuid

from django.db import models
from django.contrib.auth import get_user_model

from generics.utils.models import GenericModel

User = get_user_model()


class Plan(GenericModel):
	TYPE_CHOICES = (
		('subscription', 'Subscription'),
		('non-subscription', 'Non-Subscription'),
	)
	MODULE_CHOICES = (
		('credit_report', 'Credit Report'),
		('bill_payment', 'Bill Payment'),
	)
	name = models.CharField(max_length=255)
	type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='non-subscription')
	module = models.CharField(max_length=50, choices=MODULE_CHOICES)
	duration_days = models.IntegerField(null=True, blank=True)
	price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
	
	def __str__(self):
		return self.name


class Subscription(models.Model):
	id = models.BigAutoField(primary_key=True)
	user = models.ForeignKey(User, on_delete=models.PROTECT)
	plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
	start_date = models.DateField()
	end_date = models.DateField()
	is_active = models.BooleanField(default=True)
	autopay = models.BooleanField(default=False)  # Autopay option
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)
	transaction = models.ForeignKey('Transaction', on_delete=models.SET_NULL, null=True, blank=True, related_name='subscriptions')
	
	def __str__(self):
		return f"{self.user.mobile} - {self.plan.name}"


class PaymentMethod(GenericModel):
	TYPE_CHOICES = (
		('M-Pesa', 'M-Pesa'),
		('Airtel Money', 'Airtel Money'),
		# ('Wallet', 'Wallet'),
	)
	type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='M-Pesa')
	details = models.TextField(null=True, blank=True)
	
	def __str__(self):
		return f"{self.id} - {self.type}"


class Transaction(GenericModel):
	pkid = models.BigAutoField(primary_key=True, editable=False, db_index=True)  # pseudo primary key
	id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
	user = models.ForeignKey(User, on_delete=models.PROTECT, db_index=True)
	plan = models.ForeignKey(Plan, on_delete=models.PROTECT, null=True, blank=True)
	subscription = models.ForeignKey(Subscription, on_delete=models.PROTECT, null=True, blank=True, related_name='payment_transactions')
	payment_method = models.ForeignKey(PaymentMethod, on_delete=models.PROTECT, null=True, blank=True)
	type = models.CharField(max_length=30, db_index=True)  # Could refine this with choices if needed
	amount = models.DecimalField(max_digits=10, decimal_places=2)
	STATUS_CHOICES = (
		('initiated', 'Initiated'),
		('pending', 'Pending'),
		('successful', 'Successful'),
		('failed', 'Failed'),
	)
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, db_index=True)
	response = models.JSONField(null=True, blank=True)  # Store transaction response JSON
	mpesa_merchant_request_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
	mpesa_checkout_request_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
	mpesa_receipt_number = models.CharField(max_length=255, null=True, blank=True)
	mpesa_timestamp = models.CharField(max_length=14, blank=True, null=True)
	
	def __str__(self):
		return f"Transaction {self.id} - {self.status}"
	
	def get_amount_as_int(self):
		return str(int(self.amount))
	
	def save(self, *args, **kwargs):
		# Prefill the 'type' field with the plan name if a plan is associated with the transaction
		if self.plan and not self.type:
			self.type = self.plan.name
		super(Transaction, self).save(*args, **kwargs)
