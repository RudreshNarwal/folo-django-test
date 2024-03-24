from django.contrib import admin

from .models import PaymentMethod, Plan, Subscription, Transaction


class PaymentsAdmin(admin.ModelAdmin):

    admin.site.register(Transaction)
    admin.site.register(Plan)
    admin.site.register(PaymentMethod)
    admin.site.register(Subscription)