from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _ # gettext lazy is used as interlization or translation method in django

class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core_apps.users"
    verbose_name = _("User") # Human readable name -> from django meta library
    verbose_name_plural = _("Users")