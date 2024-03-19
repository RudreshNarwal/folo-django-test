from django.db import models
# from django.contrib.auth.models import User
from django.contrib.auth import get_user_model

User = get_user_model()

class CreditReport(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="credit_reports")
    registration_response_code = models.IntegerField(null=True, blank=True)
    credit_score = models.IntegerField(null=True, blank=True)
    grade = models.CharField(max_length=10, null=True, blank=True)
    risk_classification = models.CharField(max_length=255, null=True, blank=True)
    message_credit_risk_score = models.TextField(null=True, blank=True)
    total_npa = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total_pa = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    tol = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    message_total_loan_outstanding = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.user} - Score: {self.credit_score} - Grade: {self.grade}"
