from django.utils.translation import gettext_lazy as _
from django.db import models
from django.conf import settings
from generics.utils.models import GenericModel


class Customer(GenericModel):
    """
    Represents a customer with associated statuses and provider details.

    This class serves as a data model to store and manage customer-related
    information, including their identifier, current status, associated user,
    and provider details. It includes enumerations for possible statuses
    and providers, ensuring consistency and validation for the stored attributes.

    Attributes:
        user (ForeignKey): The user associated with this customer. This establishes
            a relationship with the AUTH_USER_MODEL and ensures that there is
            a reference to the user in the database. The related name for this
            field is 'wallet_customer'.
        customer_id (CharField): A unique identifier for the customer,
            represented as a string with a maximum length of 128.
        current_status (CharField): Represents the current status of the customer,
            using predefined choices from the CurrentStatus enumeration.
            It has a maximum length of 20.
        provider (CharField): Indicates the provider associated with the
            customer, constrained by the predefined choices in the Provider
            enumeration. This field has a maximum length of 128.
    """
    class CurrentStatus(models.TextChoices):
        NA = ("N/A", _("N/A"))
        ACTIVE = ("Active", _("Active"))
        AWAITING_QUESTIONNAIRE = ("Awaiting Questionnaire", _("Awaiting Questionnaire"))
        AWAITING_UBO = ("Awaiting UBO", _("Awaiting UBO"))
        INCOMPLETE = ("Incomplete", _("Incomplete"))
        NOT_STARTED = ("Not Started", _("Not Started"))
        OFFBOARDED = ("Offboarded", _("Offboarded"))
        PAUSED = ("Paused", _("Paused"))
        REJECTED = ("Rejected", _("Rejected"))
        UNDER_REVIEW = ("Under Review", _("Under Review"))

    class Provider(models.TextChoices):
        BRIDGE = ("Bridge", _("Bridge"))

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name='wallet_customer', on_delete=models.PROTECT
    )
    customer_id = models.CharField(max_length=128, null=True, blank=True)
    current_status = models.CharField(
        verbose_name=_("current_status"),
        choices=CurrentStatus.choices,
        max_length=128,
        default=CurrentStatus.NA,
    )
    provider = models.CharField(
        verbose_name=_("provider"),
        choices=Provider.choices,
        max_length=128,
        default=Provider.BRIDGE,
    )
    signed_agreement_id = models.CharField(max_length=255)

    def __str__(self):
        return self.user.username

    class Meta:
        """
        Meta options for the Customer model.
        """
        db_table = "international_customer"
        verbose_name = "International Customer"
        verbose_name_plural = "International Customers"
