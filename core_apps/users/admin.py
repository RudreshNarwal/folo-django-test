from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .forms import UserChangeForm, UserCreationForm
from .models import User
from drf_yasg.utils import swagger_auto_schema


class UserAdmin(BaseUserAdmin):
	ordering = ["email"]
	form = UserChangeForm
	add_form = UserCreationForm
	model = User
	
	list_display = [
		"pkid",
		"id",
		"mobile",
		"email",
		"first_name",
		"last_name",
		"is_staff",
		"is_active",
	]
	
	list_display_links = ["pkid", "id", "mobile", "email"]
	
	list_filter = ["mobile", "email", "is_staff", "is_active"]  # filter available on right side of page
	
	fieldsets = (
		(_("Login Credentials"), {"fields": ("mobile", "password")}),
		(_("Personal Info"), {"fields": ("first_name", "last_name", "email")}),
		(
			_("Permissions and Groups"),
			{
				"fields": (
					"is_active",
					"is_staff",
					"is_superuser",
					"groups",
					"user_permissions",
				)
			},
		),
		(_("Important Dates"), {"fields": ("last_login", "date_joined")}),
	)
	add_fieldsets = (
		None,
		{
			"classes": ("wide",),
			"fields": ("email", "first_name", "mobile", "last_name", "password1", "password2", "country", "city", "gender"),
		},
	)
	search_fields = ["email", "mobile", "first_name", "last_name"]


admin.site.register(User, UserAdmin)
