# core_apps/users/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .apis.user import UploadDocumentAPIView, SaveAddressAPIView

router = DefaultRouter()

urlpatterns = [
    path('', include(router.urls)),
    path('upload-document/', UploadDocumentAPIView.as_view(), name='upload_document'),
    path('save-address/', SaveAddressAPIView.as_view(), name='save_address'),
]
