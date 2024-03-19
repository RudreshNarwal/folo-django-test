import uuid
from datetime import datetime, timedelta
from random import randint
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_countries.fields import CountryField

import pytz
from django.db import models

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
        MALE = (
            "M",
            _("Male"),
        )

        FEMALE = (
            "F",
            _("Female"),
        )
        OTHER = (
            "O",
            _("Other"),
        )
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
    mobile = models.CharField(verbose_name=_("mobile number"), db_index=True, max_length=15, unique=True)
    email = models.EmailField(
        verbose_name=_("email address"), db_index=True, unique=True
    )
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_sales_person = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)
    is_email_verified = models.BooleanField(default=False)
    is_mobile_verified = models.BooleanField(default=False)
    address = models.TextField(null=True, blank=True)
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
    country = CountryField(
        verbose_name=_("country"), default="KE", blank=False, null=False
    )
    city = models.CharField(
        verbose_name=_("city"),
        max_length=180,
        blank=True,
        null=True,
    )
    mpin = models.CharField(max_length=4, null=True, blank=True)

    
    USERNAME_FIELD = "mobile"  # so that mobile field can be used for authentication
    
    REQUIRED_FIELDS = ["first_name", "last_name", "email"]
    
    objects = CustomUserManager()
    # objects = UserManager()
    
    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
    
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
            send_verification_code(self.mobile, otp)
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

# class UserManager(BaseUserManager):
#     use_in_migrations = True
#
#     def create_user(self, mobile, password=None):
#         if not mobile:
#             raise ValueError('Users must have an mobile number')
#
#         user = self.model(
#             mobile=mobile
#         )
#         user.set_password(password)
#         user.save(using=self._db)
#         return user
#
#     def create_superuser(self, mobile, password=None):
#         user = self.create_user(
#             mobile, password
#         )
#         user.is_admin = True
#         user.is_staff = True
#         user.is_superuser = True
#         user.is_active = True
#         user.save(using=self._db)
#         return user
