from django.utils import timezone
from django.db.models import Q

from core_apps.users.models import User
from core_apps.users.utils import generate_presigned_url
from core_apps.wallet.models import CustomerProfile, Wallet, WalletStatus


class DashboardMetricsService:
    """Service class for calculating dashboard metrics."""

    @staticmethod
    def get_total_users():
        """Get total number of registered users."""
        return User.objects.count()

    @staticmethod
    def get_active_wallets():
        """Get count of active wallets."""
        return Wallet.objects.filter(status=WalletStatus.ACTIVE).count()

    @staticmethod
    def get_pending_kyc():
        """Get count of pending KYC applications."""
        return CustomerProfile.objects.filter(kyc_status='PENDING').count()

    @staticmethod
    def get_failed_wallets():
        """
        Get count of wallets with error statuses.
        Includes: INACTIVE, SUSPENDED, CLOSED, LOCKED, CANCELED, CANCELLED, BARRED
        """
        error_statuses = [
            WalletStatus.INACTIVE,
            WalletStatus.SUSPENDED,
            WalletStatus.CLOSED,
            WalletStatus.LOCKED,
            WalletStatus.CANCELED,
            WalletStatus.CANCELLED,
            WalletStatus.BARRED,
        ]
        return Wallet.objects.filter(status__in=error_statuses).count()

    @staticmethod
    def get_todays_registrations():
        """Get count of users registered today."""
        today = timezone.now().date()
        return User.objects.filter(date_joined__date=today).count()

    @staticmethod
    def get_successful_onboardings():
        """
        Get count of users who have completed onboarding successfully.
        Criteria: KYC approved and wallet active.
        """
        return Wallet.objects.filter(
            status=WalletStatus.ACTIVE,
            customer__kyc_status='APPROVED'
        ).count()

    @classmethod
    def get_all_metrics(cls):
        """Get all dashboard metrics in a single call."""
        return {
            'total_users': cls.get_total_users(),
            'active_wallets': cls.get_active_wallets(),
            'pending_kyc': cls.get_pending_kyc(),
            'failed_wallets': cls.get_failed_wallets(),
            'todays_registrations': cls.get_todays_registrations(),
            'successful_onboardings': cls.get_successful_onboardings(),
        }


class CustomerOnboardingService:
    """Service class for customer onboarding data."""

    RATIFY_URL = "https://api.astraafrica.co/devadmin-portal/authentication/signin"

    @staticmethod
    def get_onboarding_queryset(filters=None):
        """
        Get customer onboarding data with optional filters.

        Args:
            filters: dict with optional keys:
                - kyc_status: list of str (PENDING, APPROVED, FAILED)
                - wallet_status: list of str (ACTIVE, INACTIVE, etc.)
                - has_error: bool
                - date_from: date
                - date_to: date
                - search: str (searches user mobile, customer_id)

        Returns:
            QuerySet of User objects with related data
        """
        queryset = User.objects.select_related(
            'customer_profile',
        ).prefetch_related(
            'customer_profile__wallets',
            'documents'
        ).order_by('-date_joined')

        if not filters:
            return queryset

        # Filter for users with customer profiles if filtering by customer-specific fields
        if filters.get('kyc_status') or filters.get('wallet_status') or filters.get('has_error'):
            queryset = queryset.filter(customer_profile__isnull=False)

        # Apply filters (now supports lists for multi-select)
        if filters.get('kyc_status'):
            kyc_statuses = filters['kyc_status']
            if isinstance(kyc_statuses, list):
                queryset = queryset.filter(
                    customer_profile__kyc_status__in=kyc_statuses
                )
            else:
                queryset = queryset.filter(
                    customer_profile__kyc_status=kyc_statuses
                )

        if filters.get('wallet_status'):
            wallet_statuses = filters['wallet_status']
            if isinstance(wallet_statuses, list):
                queryset = queryset.filter(
                    customer_profile__wallets__status__in=wallet_statuses
                )
            else:
                queryset = queryset.filter(
                    customer_profile__wallets__status=wallet_statuses
                )

        if filters.get('has_error'):
            error_statuses = [
                WalletStatus.INACTIVE,
                WalletStatus.SUSPENDED,
                WalletStatus.CLOSED,
                WalletStatus.LOCKED,
                WalletStatus.CANCELED,
                WalletStatus.CANCELLED,
                WalletStatus.BARRED,
            ]
            queryset = queryset.filter(
                Q(customer_profile__wallets__status__in=error_statuses) |
                Q(customer_profile__kyc_status='FAILED')
            )

        if filters.get('date_from'):
            queryset = queryset.filter(date_joined__date__gte=filters['date_from'])

        if filters.get('date_to'):
            queryset = queryset.filter(date_joined__date__lte=filters['date_to'])

        if filters.get('search'):
            search_term = filters['search']
            queryset = queryset.filter(
                Q(mobile__icontains=search_term) |
                Q(customer_profile__customer_id__icontains=search_term) |
                Q(first_name__icontains=search_term) |
                Q(last_name__icontains=search_term) |
                Q(email__icontains=search_term)
            )

        return queryset.distinct()

    @classmethod
    def format_customer_data(cls, user):
        """
        Format a user object into a dictionary for display.

        Args:
            user: User object with prefetched related data

        Returns:
            dict with customer onboarding data
        """
        customer_profile = getattr(user, 'customer_profile', None)
        wallet = None

        if customer_profile:
            wallets = customer_profile.wallets.all()
            wallet = wallets.first() if wallets else None

        # Check document upload status
        documents = user.documents.all()
        has_national_id = documents.filter(document_type='NATIONAL_IDENTITY').exists()
        has_facial_photo = documents.filter(document_type='FACIAL_PHOTO').exists()
        docs_uploaded = has_national_id and has_facial_photo

        # Determine if row should be highlighted (has errors)
        has_error = False
        if customer_profile and customer_profile.kyc_status == 'FAILED':
            has_error = True
        if wallet and wallet.status not in [WalletStatus.ACTIVE, WalletStatus.PENDING]:
            has_error = True

        # Check if this is a recent registration (within last 24 hours)
        is_recent = (timezone.now() - user.date_joined).total_seconds() < 86400

        # Determine if user needs manual ratification
        # Conditions: has details, nation_id, selfie, email, customer_id exists, but no wallet
        needs_ratification = (
            customer_profile is not None and
            customer_profile.customer_id is not None and
            customer_profile.kyc_status == 'PENDING' and
            wallet is None and
            docs_uploaded and
            user.email and
            user.nation_id
        )

        return {
            'user_id': str(user.id),
            'user_pkid': user.pkid,
            'customer_id': customer_profile.customer_id if customer_profile else None,
            'wallet_id': wallet.wallet_id if wallet else None,
            'mobile': user.mobile,
            'name': f"{user.first_name or ''} {user.last_name or ''}".strip() or user.mobile,
            'email': user.email,
            'date_joined': user.date_joined,
            'docs_uploaded': docs_uploaded,
            'kyc_status': customer_profile.kyc_status if customer_profile else 'N/A',
            'kyc_failure_stage': customer_profile.kyc_failure_stage if customer_profile else None,
            'kyc_error_message': customer_profile.kyc_error_message if customer_profile else None,
            'wallet_status': wallet.status if wallet else 'N/A',
            'wallet_balance': float(wallet.available_balance) if wallet else None,
            'has_error': has_error,
            'is_recent': is_recent,
            'needs_ratification': needs_ratification,
            'ratify_url': cls.RATIFY_URL if needs_ratification else None,
        }

    @classmethod
    def get_customer_detail(cls, user_pkid):
        """
        Get detailed customer information for the detail page.

        Args:
            user_pkid: The pkid of the user

        Returns:
            dict with comprehensive customer data or None if not found
        """
        try:
            user = User.objects.select_related(
                'customer_profile',
            ).prefetch_related(
                'customer_profile__wallets',
                'documents'
            ).get(pkid=user_pkid)
        except User.DoesNotExist:
            return None

        customer_profile = getattr(user, 'customer_profile', None)
        wallet = None

        if customer_profile:
            wallets = customer_profile.wallets.all()
            wallet = wallets.first() if wallets else None

        # Get all documents with their URLs
        documents = {}
        document_types = [
            'NATIONAL_IDENTITY',
            'BACK_OF_NATIONAL_IDENTITY',
            'FACIAL_PHOTO',
            'PASSPORT',
            'BACK_OF_PASSPORT',
            'DRIVERS_LICENSE',
            'BACK_OF_DRIVERS_LICENSE',
        ]

        for doc in user.documents.all():
            if doc.document_type in document_types:
                documents[doc.document_type] = {
                    'type': doc.document_type,
                    'url': generate_presigned_url(doc.s3_key) if doc.s3_key else None,
                    'document_number': doc.document_number,
                    'uploaded': True,
                }

        # Add missing document placeholders
        for doc_type in document_types:
            if doc_type not in documents:
                documents[doc_type] = {
                    'type': doc_type,
                    'url': None,
                    'document_number': None,
                    'uploaded': False,
                }

        # Check required docs
        has_national_id = documents.get('NATIONAL_IDENTITY', {}).get('uploaded', False)
        has_facial_photo = documents.get('FACIAL_PHOTO', {}).get('uploaded', False)
        docs_uploaded = has_national_id and has_facial_photo

        # Determine errors
        has_kyc_error = customer_profile and customer_profile.kyc_status == 'FAILED'
        has_wallet_error = wallet and wallet.status not in [WalletStatus.ACTIVE, WalletStatus.PENDING]

        # Build timeline
        timeline = cls._build_onboarding_timeline(user, customer_profile, wallet, docs_uploaded)

        # Determine if user needs manual ratification
        needs_ratification = (
            customer_profile is not None and
            customer_profile.customer_id is not None and
            customer_profile.kyc_status == 'PENDING' and
            wallet is None and
            docs_uploaded and
            user.email and
            user.nation_id
        )

        return {
            # User info
            'user_pkid': user.pkid,
            'user_id': str(user.id),
            'mobile': f"{user.country_code}{user.mobile}" if user.country_code else user.mobile,
            'email': user.email,
            'first_name': user.first_name,
            'middle_name': user.middle_name,
            'last_name': user.last_name,
            'full_name': f"{user.first_name or ''} {user.middle_name or ''} {user.last_name or ''}".strip() or user.mobile,
            'nation_id': user.nation_id,
            'dob': user.dob,
            'gender': user.gender,
            'city': user.city,
            'country': str(user.country) if user.country else None,
            'employment_status': user.employment_status,
            'account_purpose': user.account_purpose,
            'source_of_funds': user.source_of_funds,
            'date_joined': user.date_joined,
            'is_email_verified': user.is_email_verified,
            'is_mobile_verified': user.is_mobile_verified,

            # Customer profile info
            'customer_id': customer_profile.customer_id if customer_profile else None,
            'kyc_status': customer_profile.kyc_status if customer_profile else 'N/A',
            'kyc_failure_stage': customer_profile.kyc_failure_stage if customer_profile else None,
            'kyc_error_message': customer_profile.kyc_error_message if customer_profile else None,
            'customer_created_at': customer_profile.created_at if customer_profile else None,

            # Wallet info
            'wallet_id': wallet.wallet_id if wallet else None,
            'wallet_status': wallet.status if wallet else 'N/A',
            'wallet_balance': float(wallet.available_balance) if wallet else None,
            'wallet_account_number': wallet.account_number if wallet else None,
            'wallet_friendly_id': wallet.friendly_id if wallet else None,
            'wallet_created': wallet.created if wallet else None,
            'wallet_currency': wallet.currency if wallet else 'KES',

            # Documents
            'documents': documents,
            'docs_uploaded': docs_uploaded,

            # Errors
            'has_kyc_error': has_kyc_error,
            'has_wallet_error': has_wallet_error,
            'has_error': has_kyc_error or has_wallet_error,

            # Timeline
            'timeline': timeline,

            # Actions
            'needs_ratification': needs_ratification,
            'ratify_url': cls.RATIFY_URL if needs_ratification else None,
        }

    @staticmethod
    def _build_onboarding_timeline(user, customer_profile, wallet, docs_uploaded):
        """Build the onboarding timeline steps."""
        timeline = []

        # Step 1: Account Created
        timeline.append({
            'step': 1,
            'name': 'Account Created',
            'description': 'User registered on the platform',
            'status': 'completed',
            'timestamp': user.date_joined,
            'error': None,
        })

        # Step 2: Profile Completed
        profile_complete = all([
            user.first_name,
            user.last_name,
            user.dob,
            user.nation_id,
        ])
        timeline.append({
            'step': 2,
            'name': 'Profile Completed',
            'description': 'Personal details filled in',
            'status': 'completed' if profile_complete else 'pending',
            'timestamp': user.updated_on if profile_complete else None,
            'error': None,
        })

        # Step 3: Documents Uploaded
        timeline.append({
            'step': 3,
            'name': 'Documents Uploaded',
            'description': 'National ID and selfie uploaded',
            'status': 'completed' if docs_uploaded else 'pending',
            'timestamp': None,  # No specific timestamp available
            'error': None,
        })

        # Step 4: KYC Submitted
        if customer_profile:
            kyc_status = 'completed'
            kyc_error = None
            if customer_profile.kyc_status == 'PENDING':
                kyc_status = 'in_progress'
            elif customer_profile.kyc_status == 'FAILED':
                kyc_status = 'failed'
                kyc_error = customer_profile.kyc_error_message
                if customer_profile.kyc_failure_stage:
                    kyc_error = f"Stage: {customer_profile.kyc_failure_stage}. {kyc_error or ''}"

            timeline.append({
                'step': 4,
                'name': 'KYC Verification',
                'description': 'Identity verification process',
                'status': kyc_status,
                'timestamp': customer_profile.created_at,
                'error': kyc_error,
            })
        else:
            timeline.append({
                'step': 4,
                'name': 'KYC Verification',
                'description': 'Identity verification process',
                'status': 'pending',
                'timestamp': None,
                'error': None,
            })

        # Step 5: Wallet Created
        if wallet:
            wallet_status = 'completed' if wallet.status == WalletStatus.ACTIVE else 'in_progress'
            wallet_error = None
            if wallet.status not in [WalletStatus.ACTIVE, WalletStatus.PENDING]:
                wallet_status = 'failed'
                wallet_error = f"Wallet status: {wallet.status}"

            timeline.append({
                'step': 5,
                'name': 'Wallet Activated',
                'description': 'Digital wallet created and ready',
                'status': wallet_status,
                'timestamp': wallet.created,
                'error': wallet_error,
            })
        else:
            timeline.append({
                'step': 5,
                'name': 'Wallet Activated',
                'description': 'Digital wallet created and ready',
                'status': 'pending',
                'timestamp': None,
                'error': None,
            })

        return timeline
