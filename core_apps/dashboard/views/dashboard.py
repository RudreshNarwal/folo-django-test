from urllib.parse import urlencode

from django.shortcuts import render
from django.views import View
from django.core.paginator import Paginator
from django.utils.decorators import method_decorator

from ..decorators import admin_required
from ..services import DashboardMetricsService, CustomerOnboardingService


@method_decorator(admin_required, name='dispatch')
class DashboardView(View):
    """Main dashboard view with metrics and customer table."""
    template_name = 'dashboard/index.html'

    def get(self, request):
        metrics = DashboardMetricsService.get_all_metrics()

        # Get multiple values for status filters
        kyc_statuses = request.GET.getlist('kyc_status')
        wallet_statuses = request.GET.getlist('wallet_status')

        # Check if this is a fresh page load (no query params) vs explicit filter clear
        has_any_params = bool(request.GET)

        # Default to PENDING and FAILED for KYC if no params provided
        if not has_any_params:
            kyc_statuses = ['PENDING', 'FAILED']

        filters = {
            'kyc_status': kyc_statuses if kyc_statuses else None,
            'wallet_status': wallet_statuses if wallet_statuses else None,
            'has_error': request.GET.get('has_error') == 'true',
            'date_from': request.GET.get('date_from'),
            'date_to': request.GET.get('date_to'),
            'search': request.GET.get('search'),
        }

        # Remove empty filters
        filters = {k: v for k, v in filters.items() if v}

        queryset = CustomerOnboardingService.get_onboarding_queryset(filters)

        page_number = request.GET.get('page', 1)
        paginator = Paginator(queryset, 25)
        page_obj = paginator.get_page(page_number)

        customers = [
            CustomerOnboardingService.format_customer_data(user)
            for user in page_obj
        ]

        # Build query string for pagination (handles lists properly)
        query_params = []
        for key, value in filters.items():
            if isinstance(value, list):
                for v in value:
                    query_params.append((key, v))
            elif value is True:
                query_params.append((key, 'true'))
            elif value:
                query_params.append((key, value))
        filter_query_string = urlencode(query_params)

        context = {
            'metrics': metrics,
            'customers': customers,
            'page_obj': page_obj,
            'filters': filters,
            'filter_query_string': filter_query_string,
            'kyc_status_choices': ['PENDING', 'APPROVED', 'FAILED'],
            'wallet_status_choices': [
                'ACTIVE', 'INACTIVE', 'SUSPENDED', 'CLOSED',
                'LOCKED', 'CANCELED', 'CANCELLED', 'BARRED', 'PENDING'
            ],
        }

        return render(request, self.template_name, context)
