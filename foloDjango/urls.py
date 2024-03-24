from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions
from rest_framework.routers import DefaultRouter

from core_apps.payments.apis.subscription import ActiveSubscriptionAPIView
from core_apps.payments.apis.transaction import InitiateTransactionAPIView, MpesaCallbackAPIView, TransactionDetailView
from core_apps.users.apis import user, auth
from core_apps.transunion.views import CreditReportViewSet
# from core_apps.users.views import CustomUserDetailsView

schema_view = get_schema_view(
	openapi.Info(
		title="FoloMoney API",
		default_version="v1",
		description="FoloMoney",
		contact=openapi.Contact(email="rudresh.narwal20@gmail.com"),
		license=openapi.License(name="MIT License"),
	),
	public=True,
	permission_classes=(permissions.AllowAny,),
)

router = DefaultRouter()

router.register(r'api/v1/auth', auth.AuthView, basename='auth')
router.register(r'api/v1/users', user.UserViewSet, basename='users')
router.register(r'api/v1/tu', CreditReportViewSet, basename='tu')

urlpatterns = [
	path("redoc/", schema_view.with_ui("redoc", cache_timeout=0)),
	path(settings.ADMIN_URL, admin.site.urls),
	# path("api/v1/users/me/", CustomUserDetailsView.as_view(), name="user_details"),
	path('', include(router.urls)),
    path('api/v1/transaction/<int:transaction_id>/', TransactionDetailView.as_view(), name='transaction-detail'),
    path('api/v1/initiate-transaction/', InitiateTransactionAPIView.as_view(), name='initiate-transaction'),
    path('api/v1/mpesa/callback/', MpesaCallbackAPIView.as_view(), name='mpesa_callback'),
    path('api/v1/active-subscriptions/', ActiveSubscriptionAPIView.as_view(), name='active-subscriptions'),

]

admin.site.site_header = "FoloMoney API Admin"

admin.site.site_title = "FoloMoney API Admin Portal"

admin.site.index_title = "Welcome to FoloMoney API Portal"
