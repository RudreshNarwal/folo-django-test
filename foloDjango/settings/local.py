from .base import * # noqa
from .base import env

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("DJANGO_SECRET_KEY", default="sVsP1LinBegCrAxKpK45gG_u3ugDaZ9yy_rOJkzFEbI8PC9stqU",)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

CSRF_TRUSTED_ORIGINS = ["http://localhost:8080"]
ALLOWED_HOSTS = ["localhost", "0.0.0.0", "127.0.0.1"]
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True
# CORS_ALLOWED_ORIGINS = ['http://localhost:8080', "https://dev-api.folo.money"]
# CSRF_TRUSTED_ORIGINS = ['http://localhost:8080', "https://dev-api.folo.money"]

EMAIL_BACKEND = "djcelery_email.backends.CeleryEmailBackend"
EMAIL_HOST = env("EMAIL_HOST", default="mailhog")
EMAIL_PORT = env("EMAIL_PORT")
DEFAULT_FROM_EMAIL = "rudresh@ubuntuonline.co.ke"
DOMAIN = env("DOMAIN")
SITE_NAME = "FoloMoney"

TRANSUNION_UAT_USERNAME="ws_ubuntu"
TRANSUNION_UAT_PASSWORD="1K[8ee$1F@2&"
TRANSUNION_UAT_CODE="2496"
TRANSUNION_UAT_INFINITY_CODE="ke123456789"