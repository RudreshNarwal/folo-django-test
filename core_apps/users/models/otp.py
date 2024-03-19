from generics.utils.models import GenericModel
from django.db import models


class Otp(GenericModel):
    phone_no = models.BigIntegerField(null=True, blank=True)
    otp = models.PositiveIntegerField()
    expiry_datetime = models.DateTimeField()
    email = models.EmailField(null=True, blank=True)

    class Meta:
        verbose_name = 'user otp'
        verbose_name_plural = 'users otp'

    def __str__(self):
        return "{} : {}".format(self.otp, self.phone_no)

    def __unicode__(self):
        return "{} : {}".format(self.otp, self.phone_no)