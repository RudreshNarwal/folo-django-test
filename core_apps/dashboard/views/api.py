from django.http import JsonResponse
from django.views import View
from django.core.paginator import Paginator
from django.utils.decorators import method_decorator

from ..decorators import admin_required
from ..services import CustomerOnboardingService


@method_decorator(admin_required, name='dispatch')
class CustomerOnboardingAPIView(View):
    """API endpoint for fetching customer onboarding data with filters."""

    def get(self, request):
        filters = {
            'kyc_status': request.GET.get('kyc_status'),
            'wallet_status': request.GET.get('wallet_status'),
            'has_error': request.GET.get('has_error') == 'true',
            'date_from': request.GET.get('date_from'),
            'date_to': request.GET.get('date_to'),
            'search': request.GET.get('search'),
        }

        # Remove empty filters
        filters = {k: v for k, v in filters.items() if v}

        queryset = CustomerOnboardingService.get_onboarding_queryset(filters)

        page_number = request.GET.get('page', 1)
        page_size = int(request.GET.get('page_size', 25))
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page_number)

        customers = [
            CustomerOnboardingService.format_customer_data(user)
            for user in page_obj
        ]

        # Serialize dates for JSON
        for customer in customers:
            if customer['date_joined']:
                customer['date_joined'] = customer['date_joined'].isoformat()

        return JsonResponse({
            'customers': customers,
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_count': paginator.count,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
            }
        })
