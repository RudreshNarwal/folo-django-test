from django.db import models
from django.contrib.auth import get_user_model

from generics.utils.models import GenericModel

User = get_user_model()

class CreditReport(GenericModel):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="credit_reports")
    is_registered = models.BooleanField(default=False)  # New field replacing registration_response_code
    credit_score = models.IntegerField(null=True, blank=True)
    grade_response = models.JSONField(null=True, blank=True)
    tlo_response = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"{self.id}"
