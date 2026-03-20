from django.shortcuts import render, redirect
from django.contrib import messages
from django.views import View
from django.utils.decorators import method_decorator

from ..decorators import admin_required
from ..services import CustomerOnboardingService


@method_decorator(admin_required, name='dispatch')
class CustomerDetailView(View):
    """Customer detail view showing comprehensive user information."""
    template_name = 'dashboard/customer_detail.html'

    def get(self, request, user_pkid):
        customer_data = CustomerOnboardingService.get_customer_detail(user_pkid)

        if not customer_data:
            messages.error(request, "Customer not found.")
            return redirect('dashboard:index')

        return render(request, self.template_name, {'customer': customer_data})
