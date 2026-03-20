# models.py
from django.db import models


class Occupation(models.Model):
    """
    Represents a occupation, associated with a user.
    """
    name = models.CharField(max_length=1024)
    code = models.CharField(max_length=10)

    def __str__(self):
        return f"{self.name}, {self.code}"

    class Meta:
        db_table = "occupation"
        verbose_name = "Occupation"
        verbose_name_plural = "Occupations"
        ordering = ['name']
