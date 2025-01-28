# core_apps/users/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .apis.user import UploadDocumentAPIView, SaveAddressAPIView, AnalyzeIDView, CheckAnalysisStatus

router = DefaultRouter()

urlpatterns = [
    path('', include(router.urls)),
    path('upload-document/', UploadDocumentAPIView.as_view(), name='upload_document'),
    path('save-address/', SaveAddressAPIView.as_view(), name='save_address'),
    path('analyze-id/', AnalyzeIDView.as_view(), name='analyze-id'),
    path('analyze-id/status/<str:task_id>/', CheckAnalysisStatus.as_view(), name='check-analysis-status'),
]
