from core_apps.payments.models import Subscription
from django.utils.timezone import now


def deactivate_expired_subscriptions(user):
	"""Deactivate expired subscriptions for the user."""
	Subscription.objects.filter(user=user, end_date__lt=now(), is_active=True).update(is_active=False)
