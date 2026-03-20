import logging
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import login, logout
from django.views import View

from core_apps.users.models import User
from ..forms import MobileLoginForm, OTPVerifyForm

logger = logging.getLogger(__name__)


class LoginView(View):
    """Handle mobile number submission and OTP sending."""
    template_name = 'dashboard/login.html'

    def get(self, request):
        if request.user.is_authenticated and getattr(request.user, 'is_admin', False):
            return redirect('dashboard:index')

        form = MobileLoginForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = MobileLoginForm(request.POST)

        if form.is_valid():
            mobile = form.cleaned_data['mobile']
            country_code = form.cleaned_data['country_code']

            # Strip country code from mobile if present
            prefixes = ['+254', '+1', '+44', '+91', '+255', '+256', '+250']
            for prefix in prefixes:
                if mobile.startswith(prefix):
                    mobile = mobile[len(prefix):]
                    break

            # Remove leading zeros
            mobile = mobile.lstrip('0')

            try:
                user = User.objects.get(mobile=mobile)

                if not user.is_admin:
                    messages.error(request, "You do not have admin access.")
                    return render(request, self.template_name, {'form': form})

                user.send_otp()
                logger.info(f"OTP sent to admin user: {mobile}")

                request.session['pending_admin_mobile'] = mobile
                request.session['pending_admin_country_code'] = country_code

                messages.success(request, "OTP sent to your mobile number.")
                return redirect('dashboard:verify_otp')

            except User.DoesNotExist:
                messages.error(request, "No admin user found with this mobile number.")
                return render(request, self.template_name, {'form': form})

        return render(request, self.template_name, {'form': form})


class VerifyOTPView(View):
    """Handle OTP verification."""
    template_name = 'dashboard/verify_otp.html'

    def get(self, request):
        if 'pending_admin_mobile' not in request.session:
            return redirect('dashboard:login')

        form = OTPVerifyForm()
        mobile = request.session.get('pending_admin_mobile')
        return render(request, self.template_name, {
            'form': form,
            'mobile': mobile
        })

    def post(self, request):
        if 'pending_admin_mobile' not in request.session:
            return redirect('dashboard:login')

        form = OTPVerifyForm(request.POST)
        mobile = request.session.get('pending_admin_mobile')

        if form.is_valid():
            otp = form.cleaned_data['otp']

            try:
                user = User.objects.get(mobile=mobile)

                is_verified = user.verify_otp(supplied_otp=otp)

                if is_verified:
                    del request.session['pending_admin_mobile']
                    if 'pending_admin_country_code' in request.session:
                        del request.session['pending_admin_country_code']

                    login(request, user)

                    logger.info(f"Admin user logged in: {mobile}")
                    messages.success(request, f"Welcome, {user.first_name or 'Admin'}!")

                    return redirect('dashboard:index')
                else:
                    messages.error(request, "Invalid or expired OTP. Please try again.")

            except User.DoesNotExist:
                messages.error(request, "User not found.")
                return redirect('dashboard:login')

        return render(request, self.template_name, {
            'form': form,
            'mobile': mobile
        })


class LogoutView(View):
    """Handle logout."""

    def get(self, request):
        logout(request)
        messages.success(request, "You have been logged out.")
        return redirect('dashboard:login')

    def post(self, request):
        return self.get(request)
