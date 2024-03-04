import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from foloDjango.settings.base import AUTH_USER_MODEL
from core_apps.profiles.models import Profile

logger = logging.getLogger(__name__)


@receiver(post_save, sender=AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
        logger.info(f"{instance}'s profile has been created.")
        
# within our create user profile method, the instance parameter represents the specific instanc of the modal that triggered the signal.
# Then created parameter represents a boolean value that indicates whether the instance was created or updated.
# Then keyword Arguments is a dictionary that contains any additional keyword arguments that are passed