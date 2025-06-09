from django.contrib import admin

# Register your models here.
from core_apps.common.models import Country, State


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    """
    Admin interface for managing Country models.
    """
    list_display = ('name', 'code')
    search_fields = ('name', 'code')
    ordering = ('name',)
    list_filter = ('name',)


@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    """
    Admin interface for managing State models.
    """
    list_display = ('name', 'code', 'country')
    search_fields = ('name', 'code', 'country__name')
    ordering = ('name',)
    list_filter = ('country',)
    raw_id_fields = ('country',)

    def get_queryset(self, request):
        """
        Override to include related country in the queryset for better performance.
        """
        return super().get_queryset(request).select_related('country')
