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
	name = models.CharField(max_length=255)
	type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='non-subscription')
	duration_days = models.IntegerField(null=True, blank=True)
	cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
	
	def __str__(self):
		return self.name


class Subscription(models.Model):
	id = models.BigAutoField(primary_key=True)
	user = models.ForeignKey(User, on_delete=models.CASCADE)
	plan = models.ForeignKey(Plan, on_delete=models.CASCADE)
	start_date = models.DateField()
	end_date = models.DateField()
	is_active = models.BooleanField(default=True)
	autopay = models.BooleanField(default=False)  # Autopay option
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)
	
	def __str__(self):
		return f"{self.user.mobile} - {self.plan.name}"


class PaymentMethod(GenericModel):
	TYPE_CHOICES = (
		('M-Pesa', 'M-Pesa')
		# ('Airtel Money', 'Airtel Money'),
		# ('Wallet', 'Wallet'),
	)
	type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='M-Pesa')
	details = models.TextField(null=True, blank=True)
	
	def __str__(self):
		return f"{self.id} - {self.type}"


class Transaction(GenericModel):
	pkid = models.BigAutoField(primary_key=True, editable=False)  # pseudo primary key
	id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
	STATUS_CHOICES = (
		('pending', 'Pending'),
		('completed', 'Completed'),
		('failed', 'Failed'),
	)
	user = models.ForeignKey(User, on_delete=models.CASCADE)
	plan = models.ForeignKey(Plan, on_delete=models.SET_NULL, null=True, blank=True)
	subscription = models.ForeignKey(Subscription, on_delete=models.SET_NULL, null=True, blank=True)
	payment_method = models.ForeignKey(PaymentMethod, on_delete=models.SET_NULL, null=True, blank=True)
	type = models.CharField(max_length=255)  # Could refine this with choices if needed
	amount = models.DecimalField(max_digits=10, decimal_places=2)
	status = models.CharField(max_length=20, choices=STATUS_CHOICES)
	
	def __str__(self):
		return f"Transaction {self.id} - {self.status}"
