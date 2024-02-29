import uuid

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .managers import CustomUserManager


# Advantage of UUID
# Uuids are unique across space and time, meaning that Uuids are unique even if they are generated on
# different computers or different times. Uuids are not sequential, whereas auto incrementing integer primary keys are sequential.
# Uuids are not predictable, whereas auto incrementing integer primary keys are very predictable. Uuids are not easily guessable and uuids are not easily incremental and decremental.

# Disadvantage and solution for that using pseudo primary key
# At scale, they cause massive insert performance issues due to the primary key being a clustered index and two uuids are not easily sortable meaning.
# There is no quick sort by id chronology available and so the latest items will have to be found using timestamps which are innately slower than numeric IDs.
# Fortunately, these disadvantages can be avoided by implementing a pseudo primary key.
# So a pseudo primary key basically helps us avoid the disadvantages of primarily using a UUID as a primary

class User(AbstractBaseUser, PermissionsMixin):
	pkid = models.BigAutoField(primary_key=True, editable=False)  # pseudo primary key
	id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
	first_name = models.CharField(verbose_name=_("first name"), max_length=50)
	last_name = models.CharField(verbose_name=_("last name"), max_length=50)
	mobile = models.CharField(verbose_name=_("mobile number"), db_index=True, max_length=15, unique=True)
	email = models.EmailField(
		verbose_name=_("email address"), db_index=True, unique=True
	)
	is_staff = models.BooleanField(default=False)
	is_active = models.BooleanField(default=True)
	is_sales_person = models.BooleanField(default=False)
	date_joined = models.DateTimeField(default=timezone.now)
	
	USERNAME_FIELD = "mobile" # so that mobile field can be used for authentication
	
	REQUIRED_FIELDS = ["first_name", "last_name", "email"]
	
	objects = CustomUserManager()
	
	class Meta:
		verbose_name = _("user")
		verbose_name_plural = _("users")
	
	def __str__(self):
		return self.first_name + ' - ' + self.mobile
	
	@property
	def get_full_name(self):
		return f"{self.first_name.title()} {self.last_name.title()}"
	
	@property
	def get_short_name(self):
		return self.first_name

