from pathlib import Path
from datetime import timedelta
import environ

env = environ.Env()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
ROOT_DIR = Path(__file__).resolve().parent.parent.parent

APP_DIR = ROOT_DIR / 'core_apps'

# Define the path to the .env file
env_file = ROOT_DIR / '.envs/.local/.django'

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
]

LOCAL_APPS = [
	"core_apps.common",
	"core_apps.users",
	"core_apps.transunion",
	"core_apps.payments",
	# "core_apps.articles",
	# "core_apps.ratings",
	# "core_apps.bookmarks",
	# "core_apps.responses",
	# "core_apps.search",
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

ADMIN_URL = "supersecret/"

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
	"formatters": {
		"verbose": {
			"format": "%(levelname)s %(name)-12s %(asctime)s %(module)s "
			          "%(process)d %(thread)d %(message)s"
		}
	},
	"handlers": {
		"console": {
			"level": "DEBUG",
			"class": "logging.StreamHandler",
			"formatter": "verbose",
		}
	},
	"root": {"level": "INFO", "handlers": ["console"]},
}

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("DJANGO_SECRET_KEY", default="sVsP1LinBegCrAxKpK45gG_u3ugDaZ9yy_rOJkzFEbI8PC9stqU",)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

DATABASES = {"default": env.db("DATABASE_URL")}

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

BASE_URL=env("BASE_URL")

TRANSUNION_USERNAME=env("TRANSUNION_USERNAME")
TRANSUNION_PASSWORD=env("TRANSUNION_PASSWORD")
TRANSUNION_CODE=env("TRANSUNION_CODE")
TRANSUNION_INFINITY_CODE=env("TRANSUNION_INFINITY_CODE")

MPESA_PASSKEY=env("MPESA_PASSKEY")
MPESA_CLIENT_TOKEN=env("MPESA_CLIENT_TOKEN")
MPESA_BUSINESS_CODE=env("MPESA_BUSINESS_CODE")
