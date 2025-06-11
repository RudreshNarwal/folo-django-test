# models.py
from django.db import models


class Country(models.Model):
    """
    Represents a country with its name and code.
    """
    name = models.CharField(max_length=1024, unique=True)
    code = models.CharField(max_length=10, unique=True)
    postal_code_format = models.CharField(max_length=1024, null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "country"
        verbose_name = "Country"
        verbose_name_plural = "Countries"
        ordering = ['name']
