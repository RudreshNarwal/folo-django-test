AUTH_USER_MODEL = "users.User"


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
	"core_apps.profiles",
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