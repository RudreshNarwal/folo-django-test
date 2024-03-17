from django.contrib import admin

from .models import CreditReport


class TransUnionAdmin(admin.ModelAdmin):
    list_display = ["user", "registration_response_code", "credit_score", "grade", "total_npa", "total_pa", "tol"]
    list_display_links = ["user"]
    list_filter = ["user"]


admin.site.register(CreditReport, TransUnionAdmin)