from .base import * # noqa
from .base import env

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("DJANGO_SECRET_KEY", default="sVsP1LinBegCrAxKpK45gG_u3ugDaZ9yy_rOJkzFEbI8PC9stqU",)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

CSRF_TRUSTED_ORIGINS = ["http://localhost:8080"]

ALLOWED_HOSTS = ["localhost", "0.0.0.0", "127.0.0.1"]

EMAIL_BACKEND = "djcelery_email.backends.CeleryEmailBackend"
EMAIL_HOST = env("EMAIL_HOST", default="mailhog")
EMAIL_PORT = env("EMAIL_PORT")
DEFAULT_FROM_EMAIL = "rudresh@ubuntuonline.co.ke"
DOMAIN = env("DOMAIN")
SITE_NAME = "FoloMoney-Core"