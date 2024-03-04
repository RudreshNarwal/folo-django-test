import os

from celery import Celery
from django.conf import settings

# TODO: change this in production
os.environ.setdefault("DJANGO_SETTINGS_MODULE", ".settings.local")

app = Celery("FoloMoney")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)