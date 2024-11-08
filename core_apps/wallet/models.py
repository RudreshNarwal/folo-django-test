from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django_countries.fields import CountryField
from generics.utils.models import GenericModel
from core_apps.users.models.user import Document

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
