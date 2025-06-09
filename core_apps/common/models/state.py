# models.py
from django.db import models
from .country import Country


class State(models.Model):
    """
    Represents a state, associated with a country.
    """
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10)
    country = models.ForeignKey(Country, related_name='states', on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.name}, {self.country.name}"

    class Meta:
        db_table = "state"
        verbose_name = "State"
        verbose_name_plural = "States"
        ordering = ['name']
        unique_together = ('code', 'country')
