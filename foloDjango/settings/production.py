from pathlib import Path
from datetime import timedelta
import environ

env = environ.Env()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
ROOT_DIR = Path(__file__).resolve().parent.parent.parent

APP_DIR = ROOT_DIR / 'core_apps'

# Define the path to the .env file
env_file = ROOT_DIR / '.envs/.production/.django'

# Check if the .env file exists and then read it
if env_file.is_file():
	environ.Env.read_env(str(env_file))

DEBUG = env.bool('DJANGO_DEBUG', False)

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.1/howto/deployment/checklist/

ROOT_URLCONF = "foloDjango.urls"

DJANGO_APPS = [
	"django.contrib.admin",
	"django.contrib.auth",
	"django.contrib.contenttypes",
	"django.contrib.sessions",
	"django.contrib.messages",
	"django.contrib.staticfiles",
	"django.contrib.sites",
]

THIRD_PARTY_APPS = [
	"rest_framework",
	"django_filters",
	"django_countries",
	"phonenumber_field",
	"drf_yasg",
	"corsheaders",
	"djcelery_email",
	'rest_framework_simplejwt',
	"rest_framework.authtoken",
	"django_ses"
]

LOCAL_APPS = [
	"core_apps.common",
	"core_apps.users",
	"core_apps.transunion",
	"core_apps.payments",
	"core_apps.wallet",
	"core_apps.international_wallet",
	"core_apps.dashboard",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
	"django.middleware.security.SecurityMiddleware",
	"corsheaders.middleware.CorsMiddleware",
	"django.contrib.sessions.middleware.SessionMiddleware",
	"whitenoise.middleware.WhiteNoiseMiddleware",
	"django.middleware.common.CommonMiddleware",
	"django.middleware.csrf.CsrfViewMiddleware",
	"django.contrib.auth.middleware.AuthenticationMiddleware",
	"django.contrib.messages.middleware.MessageMiddleware",
	"django.middleware.clickjacking.XFrameOptionsMiddleware",
]

TEMPLATES = [
	{
		"BACKEND": "django.template.backends.django.DjangoTemplates",
		"DIRS": [ROOT_DIR / 'templates']
		,
		"APP_DIRS": True,
		"OPTIONS": {
			"context_processors": [
				"django.template.context_processors.debug",
				"django.template.context_processors.request",
				"django.contrib.auth.context_processors.auth",
				"django.contrib.messages.context_processors.messages",
			],
		},
	},
]

WSGI_APPLICATION = "foloDjango.wsgi.application"

# Database
# https://docs.djangoproject.com/en/4.1/ref/settings/#databases

# DATABASES = {
# 	"default": {
# 		"ENGINE": "django.db.backends.sqlite3",
# 		"NAME": ROOT_DIR / "db.sqlite3",
# 	}
# }

# DATABASES["default"]["ATOMIC_REQUESTS"] = True

PASSWORD_HASHERS = [
	"django.contrib.auth.hashers.Argon2PasswordHasher",
	"django.contrib.auth.hashers.PBKDF2PasswordHasher",
	"django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
	"django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]

# Password validation
# https://docs.djangoproject.com/en/4.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
	{
		"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
	},
	{
		"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
	},
	{
		"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
	},
	{
		"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
	},
]

# Internationalization
# https://docs.djangoproject.com/en/4.1/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

SITE_ID = 1  # default site for the project is 1

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.1/howto/static-files/

STATIC_URL = "/staticfiles/"
STATIC_ROOT = str(ROOT_DIR / "staticfiles")

MEDIA_URL = "/mediafiles/"
MEDIA_ROOT = str(ROOT_DIR / "mediafiles")

# Default primary key field type
# https://docs.djangoproject.com/en/4.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
CORS_URLS_REGEX = r"^/api/.*$"
AUTH_USER_MODEL = "users.User"

CELERY_BROKER_URL = env("CELERY_BROKER")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_RESULT_BACKEND_MAX_RETRIES = 10
CELERY_TASK_SEND_SENT_EVENT = True

if USE_TZ:
	CELERY_TIMEZONE = TIME_ZONE

REST_FRAMEWORK = {
	"DEFAULT_AUTHENTICATION_CLASSES": [
		"dj_rest_auth.jwt_auth.JWTCookieAuthentication",
	],
	"DEFAULT_PERMISSION_CLASSES": [
		"rest_framework.permissions.IsAuthenticated",
	],
	"DEFAULT_FILTER_BACKENDS": [
		"django_filters.rest_framework.DjangoFilterBackend",
	],
}

SIMPLE_JWT = {
	'ACCESS_TOKEN_LIFETIME': timedelta(days=365),
	'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
	'AUTH_HEADER_TYPES': ('Bearer',),
	'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
	'USER_ID_FIELD': 'id',
	'USER_ID_CLAIM': 'user_id',
	'USER_AUTHENTICATION_RULE': 'rest_framework_simplejwt.authentication.default_user_authentication_rule',
	'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
	'TOKEN_TYPE_CLAIM': 'token_type',
	'TOKEN_USER_CLASS': 'rest_framework_simplejwt.models.TokenUser',
	'JTI_CLAIM': 'jti',
	"SIGNING_KEY": env("SIGNING_KEY"),
}

LOGGING = {
	"version": 1,
	"disable_existing_loggers": False,
	"filters": {
		"require_debug_false": {
			"()": "django.utils.log.RequireDebugFalse"
		}
	},
	"formatters": {
		"verbose": {
			"format": "%(levelname)s %(asctime)s %(module)s "
			          "%(process)d %(thread)d %(message)s"
		},
		"simple": {
			"format": "%(levelname)s %(message)s"
		},
	},
	"handlers": {
		"mail_admins": {
			"level": "ERROR",
			"filters": ["require_debug_false"],
			"class": "django.utils.log.AdminEmailHandler",
		},
		"console": {
			"level": "DEBUG",
			"class": "logging.StreamHandler",
			"formatter": "verbose",
		},
		"celery": {
			"level": "INFO",
			"class": "logging.StreamHandler",
			"formatter": "simple",
			"stream": "ext://sys.stdout",  # Ensures log output goes to standard output
		}
	},
	"root": {
		"level": "INFO",
		"handlers": ["console"]
	},
	"loggers": {
		"django": {
			"handlers": ["console"],
			"level": "INFO",
			"propagate": True,
		},
		"django.request": {
			"handlers": ["mail_admins"],
			"level": "ERROR",
			"propagate": True,
		},
		"django.security.DisallowedHost": {
			"handlers": ["console", "mail_admins"],
			"level": "ERROR",
			"propagate": True,
		},
		"celery": {
			"handlers": ["celery"],
			"level": "INFO",
			"propagate": False
		}
	},
}

# TODO add domain names of the production server
CSRF_TRUSTED_ORIGINS = ["https://folo.money"]
SECRET_KEY = env("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["folo.money"]) + ["api.astraafrica.co", "api.africastalking.com", "localhost", "0.0.0.0", "127.0.0.1"]
CORS_ALLOW_ALL_ORIGINS = True  # set false for prod TODO
CORS_ALLOW_CREDENTIALS = True  # set false for prod TODO
ADMIN_URL = env("DJANGO_ADMIN_URL")
DATABASES = {"default": env.db("DATABASE_URL")}
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# TODO: change to 518400 later
SECURE_HSTS_SECONDS = 518400
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(
	"DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True
)

SECURE_CONTENT_TYPE_NOSNIFF = env.bool(
	"DJANGO_SECURE_CONTENT_TYPE_NOSNIFF", default=True
)

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

DEFAULT_FROM_EMAIL = env(
	"DJANGO_DEFAULT_FROM_EMAIL",
	default="FoloMoney Production <rudresh@ubuntuonline.co.ke>",
)
DEFAULT_EMAIL_RECEIVERS = ["rudresh@ubuntuonline.co.ke", "kevin@ubuntuonline.co.ke", "rudresh.narwal20@gmail.com"]

SITE_NAME = "FoloMoney"

EMAIL_SUBJECT_PREFIX = env(
	"DJANGO_EMAIL_SUBJECT_PREFIX",
	default="[FoloMoney]",
)

# settings.py

EMAIL_BACKEND = "djcelery_email.backends.CeleryEmailBackend"
CELERY_EMAIL_BACKEND = "django_ses.SESBackend"

ADMINS = [("Kevin", "kevin@ubuntuonline.co.ke"), ("Rudresh", "rudresh@ubuntuonline.co.ke"),
          ]
AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY")
AWS_SES_REGION_NAME = 'af-south-1'
AWS_SES_REGION_ENDPOINT = 'email.af-south-1.amazonaws.com'
AWS_SES_AUTO_THROTTLE = 0.5  # Throttle sending rate for production
EMAIL_USE_TLS = True
DOMAIN = env("DOMAIN")

BASE_URL = env("BASE_URL")

TRANSUNION_ENDPOINT = env("TRANSUNION_ENDPOINT")
TRANSUNION_USERNAME = env("TRANSUNION_USERNAME")
TRANSUNION_PASSWORD = env("TRANSUNION_PASSWORD")
TRANSUNION_CODE = env("TRANSUNION_CODE")
TRANSUNION_INFINITY_CODE = env("TRANSUNION_INFINITY_CODE")

MPESA_ENDPOINT = env("MPESA_ENDPOINT")
MPESA_PASSKEY = env("MPESA_PASSKEY")
MPESA_CLIENT_TOKEN = env("MPESA_CLIENT_TOKEN")
MPESA_BUSINESS_CODE = env("MPESA_BUSINESS_CODE")

AWS_STORAGE_BUCKET_NAME=env("AWS_STORAGE_BUCKET_NAME")
AWS_S3_REGION_NAME=env("AWS_S3_REGION_NAME")

OPENAI_API_KEY = env("OPENAI_API_KEY")

ADD_MONEY_WEBHOOK_URL = env("ADD_MONEY_WEBHOOK_URL")
BANK_TRANSFER_CALLBACK_URL = env("BANK_TRANSFER_CALLBACK_URL")
WALLET_WITHDRAWAL_CALLBACK_URL = env("WALLET_WITHDRAWAL_CALLBACK_URL")
WALLET_MOVEMENT_CALLBACK_URL = env("WALLET_MOVEMENT_CALLBACK_URL")
REQUESTS_VERIFY_SSL = True

AFRICA_TALKING_BASE_URL = env("AFRICA_TALKING_BASE_URL")
AFRICA_TALKING_API_KEY = env("AFRICA_TALKING_API_KEY")

BRIDGE_API_KEY = env("BRIDGE_API_KEY")
BRIDGE_BASE_URL = env("BRIDGE_BASE_URL")

TWILIO_SID = env("TWILIO_SID")
TWILIO_AUTH_TOKEN = env("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = env("TWILIO_PHONE_NUMBER")

FERNET_KEY = env("FERNET_KEY")

# Celery Beat Configuration
CELERY_BEAT_SCHEDULE = {
    'cleanup-expired-transactions': {
        'task': 'core_apps.wallet.tasks.cleanup_expired_transactions',
        'schedule': 3600.0,  # Run every hour (3600 seconds)
    },
}
CELERY_TIMEZONE = 'UTC'

WEBHOOK_PUBLIC_KEY = env("WEBHOOK_PUBLIC_KEY")
