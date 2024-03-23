from django.contrib import admin

from .models import PaymentMethod, Plan, Subscription, Transaction


class PaymentsAdmin(admin.ModelAdmin):
    list_display = ["user", "status"]
    list_display_links = ["user"]
    list_filter = ["user"]


admin.site.register(Transaction, PaymentsAdmin)
admin.site.register(Plan, PaymentsAdmin)
admin.site.register(PaymentMethod, PaymentsAdmin)
admin.site.register(Subscription, PaymentsAdmin)