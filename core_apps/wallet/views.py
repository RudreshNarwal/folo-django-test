# wallet/views.py
import uuid

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from core_apps.users.models.user import User, Document, Address
from .models import CustomerProfile, ProviderDocument
from .services.dtb_services import DTBService
from ..users.utils import get_base64_from_s3
from django.db import transaction
import logging

logger = logging.getLogger(__name__)


class FinalizeRegistrationAPIView(APIView):
    """
    Finalize Registration: Register with DTB API
    """
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        user = request.user
        try:
            customer_profile = CustomerProfile.objects.get(user=user)
        except CustomerProfile.DoesNotExist:
            return Response({"error": "Customer profile not found."}, status=status.HTTP_404_NOT_FOUND)

        if not customer_profile.external_unique_id:
            customer_profile.external_unique_id = uuid.uuid4()
            customer_profile.save()

        kyc_service = DTBService()
        try:
            kyc_service.authenticate()

            # Prepare customer data
            customer_data = {
                "dateOfBirth": user.dob.strftime('%Y%m%d') if user.dob else '19700101',
                "externalUniqueId": str(customer_profile.external_unique_id),
                "firstName": user.first_name,
                "lastName": user.last_name,
                "locale": "EN",
                "phone1": f"{user.country_code.replace('+', '')}{user.mobile}",
                "status": "ACTIVE",
                "gender": user.gender or "M",
                "maritalStatus": user.marital_status or "SINGLE",
                "birthCountry": user.country.code if user.country else "KE",
                "birthCity": user.city or "Nairobi",
                "nationalIdentityNumber": user.nation_id or "123456",
                "title": user.title or "Mr."
            }

            # Register customer with KYC provider
            kyc_response = kyc_service.register_customer(customer_data)
            customer_profile.provider_customer_id = kyc_response.get('customerId')
            customer_profile.save()

            # Upload documents to KYC provider
            documents = Document.objects.filter(user=user)
            for doc in documents:
                base64_encoded_document = get_base64_from_s3(doc.s3_key)
                document_data = {
                    "base64EncodedDocument": base64_encoded_document,
                    "documentType": doc.document_type,
                    "mediaType": doc.media_type
                }
                doc_response = kyc_service.add_document(customer_profile.provider_customer_id, document_data)
                # Save provider_document_id in wallet app
                ProviderDocument.objects.create(
                    document=doc,
                    provider_document_id=doc_response.get('documentId')
                )

            # Add address to KYC provider
            try:
                address = Address.objects.get(user=user)
                address_data = {
                    "addressType": address.address_type,
                    "city": address.city,
                    "country": address.country.code,
                    "line1": address.line1,
                    "line2": address.line2,
                    "state": address.state,
                    "code": address.code
                }
                kyc_service.add_address(customer_profile.provider_customer_id, address_data)
            except Address.DoesNotExist:
                logger.warning(f"No address found for user {user.id}. Skipping address addition to KYC.")

            # Ratify KYC
            kyc_result = kyc_service.ratify_kyc(customer_profile.provider_customer_id)
            # Process KYC response and update status
            kyc_passed = all(
                check.get('passed', False)
                for check in kyc_result.values()
                if isinstance(check, dict) and check.get('checked', False)
            )
            customer_profile.kyc_status = 'APPROVED' if kyc_passed else 'FAILED'
            customer_profile.save()

            return Response({
                "message": "Registration and KYC completed",
                "kyc_status": customer_profile.kyc_status
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error during KYC registration: {e}")
            # Handle fallback scenario
            customer_profile.kyc_status = 'FAILED'
            customer_profile.kyc_failure_stage = 'Registration/KYC'
            customer_profile.kyc_error_message = str(e)
            customer_profile.save()
            return Response({
                "message": "Registration failed",
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
