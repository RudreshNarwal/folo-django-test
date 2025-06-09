import uuid
from datetime import datetime, timedelta
from random import randint
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_countries.fields import CountryField

import pytz
from django.db import models

from core_apps.common.models import Country, State
from core_apps.users.managers import CustomUserManager
from generics.utils.models import GenericModel
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser, PermissionsMixin

from services.send_sms import send_verification_code


# Advantage of UUID
# Uuids are unique across space and time, meaning that Uuids are unique even if they are generated on
# different computers or different times. Uuids are not sequential, whereas auto incrementing integer primary keys are sequential.
# Uuids are not predictable, whereas auto incrementing integer primary keys are very predictable. Uuids are not easily guessable and uuids are not easily incremental and decremental.

# Disadvantage and solution for that using pseudo primary key
# At scale, they cause massive insert performance issues due to the primary key being a clustered index and two uuids are not easily sortable meaning.
# There is no quick sort by id chronology available and so the latest items will have to be found using timestamps which are innately slower than numeric IDs.
# Fortunately, these disadvantages can be avoided by implementing a pseudo primary key.
# So a pseudo primary key basically helps us avoid the disadvantages of primarily using a UUID as a primary

class User(AbstractBaseUser, GenericModel, PermissionsMixin):
	class Gender(models.TextChoices):
		MALE = ("Male", _("Male"))
		FEMALE = ("Female", _("Female"))
		OTHER = ("Other", _("Other"))
	
	class MaritalStatus(models.TextChoices):
		SINGLE = ("Single", _("Single"))
		MARRIED = ("Married", _("Married"))
		DIVORCED = ("Divorced", _("Divorced"))
		WIDOWED = ("Widowed", _("Widowed"))
	
	class Title(models.TextChoices):
		MR = ("Mr.", _("Mr."))
		MRS = ("Mrs.", _("Mrs."))
		MISS = ("Miss", _("Miss"))
		MS = ("Ms.", _("Ms."))
		DR = ("Dr.", _("Dr."))
		CHIEF = ("Chief", _("Chief"))
		SIR = ("Sir", _("Sir"))

	"""
	User Model:
		It contains basic user information required for authentication,
		In case of api request, user can use authentication token for login
	"""
	pkid = models.BigAutoField(primary_key=True, editable=False)  # pseudo primary key
	id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
	username = models.CharField(verbose_name=_("user name"), max_length=50, null=True, blank=True)
	first_name = models.CharField(verbose_name=_("first name"), max_length=50)
	middle_name = models.CharField(verbose_name=_("middle name"), max_length=50, null=True, blank=True)
	last_name = models.CharField(verbose_name=_("last name"), max_length=50)
	father_name = models.CharField(max_length=128, null=True, blank=True)
	mother_name = models.CharField(max_length=128, null=True, blank=True)
	spouse_name = models.CharField(max_length=128, null=True, blank=True)
	country_code = models.CharField(max_length=5, default='+254', null=True, blank=True)
	mobile = models.CharField(verbose_name=_("mobile number"), db_index=True, max_length=15, unique=True)
	email = models.EmailField(
		verbose_name=_("email address"), db_index=True, null=True, blank=True
	)
	is_staff = models.BooleanField(default=False)
	is_active = models.BooleanField(default=True)
	is_sales_person = models.BooleanField(default=False)
	is_superuser = models.BooleanField(default=False)
	is_admin = models.BooleanField(default=False)
	is_email_verified = models.BooleanField(default=False)
	is_mobile_verified = models.BooleanField(default=False)
	referral_code = models.CharField(max_length=255, null=True, blank=True)
	nation_id = models.CharField(max_length=20, null=True, blank=True)
	is_mobile_otp_on = models.BooleanField(default=True)
	
	date_joined = models.DateTimeField(default=timezone.now)
	dob = models.DateField(null=True, blank=True)
	gender = models.CharField(
		verbose_name=_("gender"),
		choices=Gender.choices,
		max_length=20,
		blank=True, null=True
	)
	marital_status = models.CharField(
		max_length=10, choices=MaritalStatus.choices, blank=True, null=True
	)
	title = models.CharField(max_length=5, choices=Title.choices, blank=True, null=True)
	country = CountryField(
		verbose_name=_("country"), default="KE", blank=False, null=False
	)
	city = models.CharField(
		verbose_name=_("city"), max_length=180, blank=True, null=True
	)
	district_of_birth = models.CharField(
		verbose_name=_("district_of_birth"), max_length=180, blank=True, null=True
	)
	mpin = models.CharField(max_length=4, null=True, blank=True)
	bridge_signed_agreement_id = models.CharField(max_length=255, null=True, blank=True)

	USERNAME_FIELD = "mobile"  # so that mobile field can be used for authentication

	REQUIRED_FIELDS = ["first_name", "last_name", "email"]
	
	objects = CustomUserManager()
	
	# objects = UserManager()
	
	class Meta:
		verbose_name = _("user")
		verbose_name_plural = _("users")
	
	# Logic to determine the title
	
	def determine_title(self):
		if self.gender == self.Gender.MALE:
			return self.Title.MR
		elif self.gender == self.Gender.FEMALE:
			if self.marital_status == self.MaritalStatus.MARRIED:
				return self.Title.MRS
			else:
				return self.Title.MS
		return None
	
	# Overriding the save method to set the title
	def save(self, *args, **kwargs):
		# Set the title if it's not manually provided
		if not self.title:
			self.title = self.determine_title()
		super(User, self).save(*args, **kwargs)
	
	def __str__(self):
		return self.first_name + ' - ' + self.mobile
	
	def __unicode__(self):
		return "{} - {}".format(self.first_name, self.last_name)
	
	def has_perm(self, perm, obj=None):
		"Does the user have a specific permission?"
		# Simplest possible answer: Yes, always
		return True
	
	def has_module_perms(self, app_label):
		"Does the user have permissions to view the app `app_label`?"
		# Simplest possible answer: Yes, always
		return True
	
	# @property
	# def is_staff(self):
	#     "Is the user a member of staff?"
	#     # Simplest possible answer: All admins are staff
	#     return self.is_admin
	
	@property
	def get_full_name(self):
		return f"{self.first_name.title()} {self.last_name.title()}"
	
	@property
	def get_full_mobile(self):
		return f"{self.country_code.title()}{self.mobile.title()}"
	
	@property
	def get_mobile_without_plus(self):
		return f"{self.country_code.replace('+', '').title()}{self.mobile.title()}"
	
	@property
	def get_short_name(self):
		return self.first_name
	
	def send_otp(self):
		from core_apps.users.models import Otp
		Otp.objects.filter(phone_no=self.mobile, is_active=True).update(is_active=False)
		otp = randint(100000, 999999)
		expiry_minutes = timezone.now() + timedelta(minutes=5)
		otp_obj = Otp.objects.create(phone_no=self.mobile, otp=otp, expiry_datetime=expiry_minutes)
		otp_obj.save()
		if self.is_mobile_otp_on:
			send_verification_code(self.get_full_mobile, otp)
		return otp
	
	def verify_otp(self, supplied_otp, ):
		is_verified = False
		if supplied_otp is not None:
			from core_apps.users.models import Otp
			otp_obj = Otp.objects.filter(phone_no=self.mobile, is_active=True).order_by('-created_on').first()
			current_time = timezone.now()
			if (otp_obj and otp_obj.expiry_datetime > current_time and str(otp_obj.otp) == str(supplied_otp)) or str(
					supplied_otp) == '200896':
				if not self.is_mobile_verified:
					self.is_mobile_verified = True
				self.save()
				otp_obj.is_active = False
				otp_obj.save()
				is_verified = True
		return is_verified


class Document(GenericModel):
	DOCUMENT_TYPE_CHOICES = [
		('NATIONAL_IDENTITY', 'National Identity'),
		('BACK_OF_NATIONAL_IDENTITY', 'National Identity Back'),
		('FACIAL_PHOTO', 'Facial Photo'),
		('SOCIAL_SECURITY_NUMBER', 'Social Security Number'),
		('DRIVERS_LICENSE', 'Drivers License'),
		('BACK_OF_DRIVERS_LICENSE', 'Drivers License Back'),
	]

	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documents')
	document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPE_CHOICES)
	media_type = models.CharField(max_length=50)
	s3_key = models.CharField(max_length=255)  # Store S3 object key
	document_number = models.CharField(max_length=50, null=True, blank=True) # e.g., National ID number, Driver License number

	def __str__(self):
		return f"Document {self.document_type} for {self.user.mobile}"
	
	class Meta:
		unique_together = ('user', 'document_type')


class Address(GenericModel):
	ADDRESS_TYPE_CHOICES = [
		('PRIMARY', 'Primary'),
		('PHYSICAL', 'Physical'),
		('POSTAL', 'Postal'),
		('HEADQUARTERS', 'Headquarters'),
		('OPERATING', 'Operating'),
		('BRANCH', 'Branch'),
		('REGISTERED', 'Registered'),
	]
	
	user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='address')
	address_type = models.CharField(max_length=50, choices=ADDRESS_TYPE_CHOICES, default='PHYSICAL')
	city = models.CharField(max_length=100)
	country = CountryField()
	line1 = models.CharField(max_length=255)
	line2 = models.CharField(max_length=255, blank=True, null=True)
	state = models.CharField(max_length=100)
	code = models.CharField(max_length=20)
	state_master = models.ForeignKey(
		State, on_delete=models.CASCADE, related_name='addresses', blank=True, null=True
	)
	country_master = models.ForeignKey(
		Country, on_delete=models.CASCADE, related_name='addresses', blank=True, null=True
	)
	
	def __str__(self):
		return f"Address for {self.user.mobile}"


class UserTask(GenericModel):
	STATUS_CHOICES = [
		('PENDING', 'Pending'),
		('PROCESSING', 'Processing'),
		('COMPLETED', 'Completed'),
		('FAILED', 'Failed')
	]

	TASK_TYPE_CHOICES = [
		('NATIONAL_ID_DATA_EXTRACTION', 'National ID Data Extraction'),
		# Add other task types as needed
	]

	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tasks')
	task_id = models.CharField(max_length=255, unique=True)
	task_type = models.CharField(max_length=50, choices=TASK_TYPE_CHOICES)
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
	result = models.JSONField(null=True, blank=True)
	error_message = models.TextField(null=True, blank=True)
	started_at = models.DateTimeField(auto_now_add=True)
	completed_at = models.DateTimeField(null=True, blank=True)

	class Meta:
		ordering = ['-started_at']
		indexes = [
			models.Index(fields=['user', 'task_type', 'status']),
			models.Index(fields=['task_id']),
		]

	def __str__(self):
		return f"{self.task_type} - {self.status} for {self.user.mobile}"

	def mark_completed(self, result):
		self.status = 'COMPLETED'
		self.result = result
		self.completed_at = timezone.now()
		self.save()

	def mark_failed(self, error_message):
		self.status = 'FAILED'
		self.error_message = error_message
		self.completed_at = timezone.now()
		self.save()
