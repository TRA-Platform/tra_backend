import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "traApp.settings")
app = Celery("traApp")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
