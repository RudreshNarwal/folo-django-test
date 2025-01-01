# views.py

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
import logging
import uuid

from core_apps.users.models.user import User, Document, Address
from .models import CustomerProfile, ProviderDocument
from .services.dtb_services import (
    DTBService,
    DTBServiceError,
    DTBServiceAuthenticationError,
    DTBServiceAPIError,
)
from ..users.utils import get_base64_from_s3

logger = logging.getLogger(__name__)

# Constants for mapping gender & marital status
GENDER_MAPPING = {
    "MALE": "M",
    "FEMALE": "F",
    "OTHER": "O"
}

MARITAL_STATUS_MAPPING = {
    "SINGLE": "S",
    "MARRIED": "M",
    "DIVORCED": "D",
    "WIDOWED": "W"
}

def handle_provider_exception(customer_profile, stage, error):
    """
    Centralized handler for provider (DTB) exceptions during KYC.
    Sets the customer_profile as failed, saves the error, and returns an error response.
    """
    logger.error(f"Error during {stage}: {error}")
    customer_profile.kyc_status = 'FAILED'
    customer_profile.kyc_error_message = f"{stage} Error: {str(error)}"
    customer_profile.save()

    return Response(
        {
            "message": f"Registration failed at {stage} stage",
            "error": str(error)
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR
    )


class FinalizeRegistrationAPIView(APIView):
    """
    Finalize Registration: Register with DTB API
    """
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        user = request.user

        # Get or create the CustomerProfile
        customer_profile, _ = CustomerProfile.objects.get_or_create(user=user)
        if not customer_profile.external_unique_id:
            customer_profile.external_unique_id = uuid.uuid4()
            customer_profile.save()

        kyc_service = DTBService()

        try:
            # ---------------------------
            # 1. Customer Registration
            # ---------------------------
            customer_profile.kyc_failure_stage = 'Customer Registration'
            customer_profile.save()

            customer_data = {
                "dateOfBirth": user.dob.strftime('%Y%m%d'),
                "externalUniqueId": str(customer_profile.external_unique_id),
                "firstName": user.first_name,
                "lastName": user.last_name,
                "locale": "EN",
                "phone1": f"{user.country_code.replace('+', '')}{user.mobile}",
                "status": "ACTIVE",
                "gender": GENDER_MAPPING.get(user.gender.upper()),
                "maritalStatus": MARITAL_STATUS_MAPPING.get(user.marital_status.upper()),
                "birthCountry": user.country.code,
                "birthCity": user.city,
                "nationalIdentityNumber": user.nation_id,
                "title": (user.title or "Mr.").replace(".", "").upper()
            }

            try:
                kyc_response = kyc_service.register_customer(customer_data)
                customer_profile.provider_customer_id = kyc_response.get('customerId')
                customer_profile.save()
            except (DTBServiceAuthenticationError, DTBServiceAPIError, DTBServiceError) as e:
                return handle_provider_exception(customer_profile, 'Customer Registration', e)

            # ---------------------------
            # 2. Document Upload
            # ---------------------------
            customer_profile.kyc_failure_stage = 'Document Upload'
            customer_profile.save()

            documents = Document.objects.filter(
                user=user,
                document_type__in=['NATIONAL_IDENTITY', 'FACIAL_PHOTO']
            )

            for doc in documents:
                base64_encoded_document = get_base64_from_s3(doc.s3_key)
                document_data = {
                    "base64EncodedDocument": base64_encoded_document,
                    "documentType": doc.document_type,
                    "mediaType": doc.media_type
                }

                try:
                    doc_response = kyc_service.add_document(
                        customer_profile.provider_customer_id,
                        document_data
                    )
                    ProviderDocument.objects.create(
                        document=doc,
                        provider_document_id=doc_response.get('documentId')
                    )
                except (DTBServiceAuthenticationError, DTBServiceAPIError, DTBServiceError) as e:
                    return handle_provider_exception(customer_profile, 'Document Upload', e)

            # ---------------------------
            # 3. Address Addition
            # ---------------------------
            customer_profile.kyc_failure_stage = 'Address Addition'
            customer_profile.save()

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
                try:
                    kyc_service.add_address(customer_profile.provider_customer_id, address_data)
                except (DTBServiceAuthenticationError, DTBServiceAPIError, DTBServiceError) as e:
                    return handle_provider_exception(customer_profile, 'Address Addition', e)
            except Address.DoesNotExist:
                logger.warning(f"No address found for user {user.id}. Skipping address addition to KYC.")

            # ---------------------------
            # 4. KYC Ratification
            # ---------------------------
            customer_profile.kyc_failure_stage = 'KYC Ratification'
            customer_profile.save()

            try:
                kyc_result = kyc_service.ratify_kyc(customer_profile.provider_customer_id)
                kyc_passed = all(
                    check.get('passed', False)
                    for check in kyc_result.values()
                    if isinstance(check, dict) and check.get('checked', False)
                )
                customer_profile.kyc_status = 'APPROVED' if kyc_passed else 'FAILED'
                customer_profile.kyc_failure_stage = None if kyc_passed else customer_profile.kyc_failure_stage
                customer_profile.kyc_error_message = None if kyc_passed else 'Customer is not ratified'
                customer_profile.save()
            except (DTBServiceAuthenticationError, DTBServiceAPIError, DTBServiceError) as e:
                return handle_provider_exception(customer_profile, 'KYC Ratification', e)

            # If everything is successful
            return Response({
                "message": "Registration and KYC completed",
                "kyc_status": customer_profile.kyc_status
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Unexpected error during KYC registration: {e}")
            customer_profile.kyc_status = 'FAILED'
            customer_profile.kyc_failure_stage = 'Registration/KYC'
            customer_profile.kyc_error_message = str(e)
            customer_profile.save()
            return Response({
                "message": "Registration failed",
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
