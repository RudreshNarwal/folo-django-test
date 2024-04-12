from django.contrib import admin

from .models import CreditReport


class TransUnionAdmin(admin.ModelAdmin):
    list_display = ["user", "is_registered"]
    list_display_links = ["user"]
    list_filter = ["user"]


admin.site.register(CreditReport, TransUnionAdmin)