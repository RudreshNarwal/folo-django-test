# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.conf import settings
from django.db import models


class GenericModel(models.Model):
    created_on = models.DateTimeField(
        auto_now_add=True
    )
    
    updated_on = models.DateTimeField(
        auto_now=True,
        db_index=True
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True
    )

    is_active = models.BooleanField(
        default=True
    )

    class Meta:
        abstract = True


class GenericModelWithoutActive(models.Model):
    created_on = models.DateTimeField(
        auto_now_add=True
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True
    )

    updated_on = models.DateTimeField(
        auto_now=True,
        db_index=True
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True
    )

    class Meta:
        abstract = True
