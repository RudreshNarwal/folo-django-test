from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_countries.fields import CountryField

from core_apps.common.models import TimeStampedModel

User = get_user_model()


class Profile(TimeStampedModel):
    class Gender(models.TextChoices):
        MALE = (
            "M",
            _("Male"),
        )

        FEMALE = (
            "F",
            _("Female"),
        )
        OTHER = (
            "O",
            _("Other"),
        )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    gender = models.CharField(
        verbose_name=_("gender"),
        choices=Gender.choices,
        max_length=20,
	    blank=True, null=True
    )
    country = CountryField(
        verbose_name=_("country"), default="KE", blank=False, null=False
    )
    city = models.CharField(
        verbose_name=_("city"),
        max_length=180,
        blank=True,
        null=True,
    )
    profile_photo = models.CharField(
        verbose_name=_("profile photo"), max_length=400, blank=True, null=True
    )
    twitter_handle = models.CharField(
        verbose_name=_("twitter handle"), max_length=20, blank=True, null=True
    )
    followers = models.ManyToManyField(
        "self", symmetrical=False, related_name="following", blank=True, null=True
    )
    # We sent related them to following to specify the reverse relation name for the following relationship.
    # Then symmetrical is equal to false means that if profile A follows profile b, it does not imply that profile B also follows profile. A.
    # This is useful if you want to model relationships where one profile follows another, but the other profile may not necessarily reciprocate.
    # So that's why a symmetrical is a false.

    def __str__(self):
        return f"{self.user.first_name - self.user.mobile}"

    def follow(self, profile):
        self.followers.add(profile)

    def unfollow(self, profile):
        self.followers.remove(profile)

    def check_following(self, profile):
        return self.followers.filter(pkid=profile.pkid).exists()