from django.urls import path
from .views import (
    LoginView,
    VerifyOTPView,
    LogoutView,
    DashboardView,
    CustomerOnboardingAPIView,
    CustomerDetailView,
)

app_name = 'dashboard'

urlpatterns = [
    # Authentication
    path('login/', LoginView.as_view(), name='login'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify_otp'),
    path('logout/', LogoutView.as_view(), name='logout'),

    # Dashboard
    path('', DashboardView.as_view(), name='index'),
    path('customers/<int:user_pkid>/', CustomerDetailView.as_view(), name='customer_detail'),

    # API endpoints
    path('api/customers/', CustomerOnboardingAPIView.as_view(), name='api_customers'),
]
