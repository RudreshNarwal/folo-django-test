from django.core.validators import RegexValidator
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django_countries.serializers import CountryFieldMixin
from .models import CustomerProfile, ProviderDocument, TopUpTransaction, Transaction, Wallet, UserContact, WalletType, BankBeneficiary

User = get_user_model()


class UserSerializer(serializers.ModelSerializer, CountryFieldMixin):
	class Meta:
		model = User
		fields = [
			'id', 'mobile', 'first_name', 'last_name', 'email',
			'dob', 'gender', 'country_code', 'nation_id', 'city', 'country'
		]


class CustomerProfileSerializer(serializers.ModelSerializer):
	user = UserSerializer()
	
	class Meta:
		model = CustomerProfile
		fields = [
			'id', 'user', 'external_unique_id', 'kyc_status',
			'kyc_failure_stage', 'kyc_error_message'
		]


class ProviderDocumentSerializer(serializers.ModelSerializer):
	class Meta:
		model = ProviderDocument
		fields = ['provider_document_id']


class WalletResponseSerializer(serializers.ModelSerializer):
	class Meta:
		model = Wallet
		fields = [
			"account_number", "available_balance", "configuration", "created",
			"currency", "current_balance", "customer_id", "description",
			"external_unique_id", "friendly_id", "name", "organisation_id",
			"reservations", "status", "wallet_id", "wallet_type_id"
		]


class WalletSerializer(serializers.ModelSerializer):
	customer = CustomerProfileSerializer()
	has_mpin = serializers.SerializerMethodField()
	
	def get_has_mpin(self, obj):
		return obj.mpin is not None and obj.mpin != ''
	
	class Meta:
		model = Wallet
		fields = [
			'wallet_id', 'name', 'description', 'status', 'currency',
			'available_balance', 'current_balance', 'reservations', 'account_number', 'customer', 'has_mpin'
		]


class TopUpTransactionSerializer(serializers.ModelSerializer):
	class Meta:
		model = TopUpTransaction
		fields = [
			'payment_id', 'status', 'amount', 'currency', 'created_at', 'description',
		]


class WalletDetailsSerializer(serializers.ModelSerializer):
	first_name = serializers.CharField(source='user.first_name')
	last_name = serializers.CharField(source='user.last_name')
	
	class Meta:
		model = Wallet
		fields = ['first_name', 'last_name', 'account_number', 'wallet_id', 'status']


class TransactionSerializer(serializers.ModelSerializer):
	from_wallet_id = serializers.CharField(source='from_wallet.wallet_id', read_only=True, allow_null=True)
	to_wallet_id = serializers.CharField(source='to_wallet.wallet_id', read_only=True, allow_null=True)
	contact_name = serializers.CharField(source='contact.name', read_only=True, allow_null=True)
	contact_phone = serializers.CharField(source='contact.phone_number', read_only=True, allow_null=True)
	bank_beneficiary_info = serializers.SerializerMethodField()
	transaction_direction = serializers.SerializerMethodField()
	other_party_info = serializers.SerializerMethodField()
	
	class Meta:
		model = Transaction
		fields = [
			'transaction_id', 'transaction_type', 'amount', 'fee', 'currency',
			'status', 'description', 'created_at', 'from_wallet_id',
			'to_wallet_id', 'deliver_to_phone', 'gateway_transaction_id',
			'contact_name', 'contact_phone', 'bank_beneficiary_info',
			'transaction_direction', 'other_party_info'
		]
		read_only_fields = fields
	
	def get_bank_beneficiary_info(self, obj):
		"""Get bank beneficiary information for bank transfers."""
		if obj.bank_beneficiary:
			return {
				'id': obj.bank_beneficiary.id,
				'account_holder_name': obj.bank_beneficiary.account_holder_name,
				'account_number': obj.bank_beneficiary.account_number,
				'bank_name': obj.bank_beneficiary.bank_name,
				'branch_name': obj.bank_beneficiary.branch_name,
				'nickname': obj.bank_beneficiary.nickname
			}
		return None
	
	def get_transaction_direction(self, obj):
		"""Determine if this is an incoming or outgoing transaction for the current user."""
		request = self.context.get('request')
		if not request or not request.user:
			return 'UNKNOWN'
		
		try:
			user_wallet = Wallet.objects.get(user=request.user, status='ACTIVE')
		except Wallet.DoesNotExist:
			return 'UNKNOWN'
		
		# For wallet-to-wallet transfers
		if obj.transaction_type == 'WALLET_TO_WALLET':
			if obj.from_wallet == user_wallet:
				return 'OUTGOING'
			elif obj.to_wallet == user_wallet:
				return 'INCOMING'
		
		# For MPESA, bank, and PesaLink transfers (always outgoing from user's perspective)
		elif obj.transaction_type in ['WALLET_TO_MPESA', 'WALLET_TO_BANK', 'WALLET_TO_PESALINK']:
			return 'OUTGOING'
		
		# For system transactions (refunds, reversals, adjustments)
		elif obj.transaction_type in ['REFUND', 'REVERSAL', 'ADJUSTMENT']:
			if obj.to_wallet == user_wallet:
				return 'INCOMING'
			elif obj.from_wallet == user_wallet:
				return 'OUTGOING'
		
		# For fee transactions
		elif obj.transaction_type == 'FEE':
			return 'OUTGOING'  # Fees are always outgoing
		
		return 'UNKNOWN'
	
	def get_other_party_info(self, obj):
		"""Get information about the other party in the transaction."""
		request = self.context.get('request')
		if not request or not request.user:
			return None
		
		try:
			user_wallet = Wallet.objects.get(user=request.user, status='ACTIVE')
		except Wallet.DoesNotExist:
			return None
		
		# For wallet-to-wallet transfers
		if obj.transaction_type == 'WALLET_TO_WALLET':
			if obj.from_wallet == user_wallet and obj.to_wallet:
				# Outgoing - show recipient info
				return {
					'wallet_id': str(obj.to_wallet.wallet_id),
					'user_name': obj.to_wallet.user.get_full_name() if obj.to_wallet.user else None,
					'phone': obj.to_wallet.user.mobile if obj.to_wallet.user else None
				}
			elif obj.to_wallet == user_wallet and obj.from_wallet:
				# Incoming - show sender info
				return {
					'wallet_id': str(obj.from_wallet.wallet_id),
					'user_name': obj.from_wallet.user.get_full_name() if obj.from_wallet.user else None,
					'phone': obj.from_wallet.user.mobile if obj.from_wallet.user else None
				}
		
		# For MPESA transfers
		elif obj.transaction_type == 'WALLET_TO_MPESA':
			return {
				'phone': obj.deliver_to_phone,
				'contact_name': obj.contact.name if obj.contact else None
			}
		
		# For bank transfers (PesaLink and EFT)
		elif obj.transaction_type in ['WALLET_TO_BANK', 'WALLET_TO_PESALINK']:
			if obj.bank_beneficiary:
				return {
					'account_holder_name': obj.bank_beneficiary.account_holder_name,
					'account_number': obj.bank_beneficiary.account_number,
					'bank_name': obj.bank_beneficiary.bank_name,
					'branch_name': obj.bank_beneficiary.branch_name,
					'nickname': obj.bank_beneficiary.nickname
				}
		
		# For system transactions
		elif obj.transaction_type in ['REFUND', 'REVERSAL', 'ADJUSTMENT']:
			return {
				'type': 'SYSTEM',
				'description': obj.description
			}
		
		return None


class WalletToWalletTransferSerializer(serializers.Serializer):
	amount = serializers.DecimalField(max_digits=20, decimal_places=2, min_value=1)
	description = serializers.CharField(required=False, allow_blank=True)
	to_wallet_id = serializers.IntegerField()
	mpin = serializers.CharField(write_only=True, min_length=4, max_length=6)
	
	def validate_amount(self, value):
		if value <= 0:
			raise serializers.ValidationError("Amount must be greater than 0")
		return value
	
	def validate(self, data):
		# Get the user context from the serializer context
		request = self.context.get('request')
		if not request or not request.user.is_authenticated:
			raise serializers.ValidationError({"error": "Authentication required"})
		
		user = request.user
		
		# Get the user's active wallet
		try:
			wallet = Wallet.objects.get(user=user, status='ACTIVE')
		except Wallet.DoesNotExist:
			raise serializers.ValidationError({"error": "No active wallet found for your account"})
		except Wallet.MultipleObjectsReturned:
			wallet = Wallet.objects.filter(user=user, status='ACTIVE').first()
		
		# Set the from_wallet_id for other validations
		self.wallet = wallet
		
		# Validate MPIN using direct comparison
		# !! SECURITY WARNING: Assumes self.wallet.mpin is appropriately handled (e.g., hashed) !!
		if not self.wallet.mpin:
			raise serializers.ValidationError({"mpin": "MPIN is not set for your wallet. Please set it first."})
		# Direct comparison:
		if data['mpin'] != self.wallet.mpin:
			raise serializers.ValidationError({"mpin": "Invalid MPIN"})
		
		# Check if wallet has sufficient balance
		if wallet.available_balance < data['amount']:
			raise serializers.ValidationError({"amount": "Insufficient balance in wallet"})
		
		return data


class WalletToMpesaTransferSerializer(serializers.Serializer):
	amount = serializers.DecimalField(
		max_digits=20, decimal_places=2, min_value=10, max_value=150000
	)
	phone_number = serializers.CharField(max_length=20)
	contact_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
	mpin = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
	description = serializers.CharField(max_length=200, required=False, allow_blank=True)
	
	def validate(self, data):
		request = self.context.get('request')
		if not request or not request.user:
			raise serializers.ValidationError("User context is required.")
		
		user = request.user
		mpin = data.get('mpin')
		
		# Validate user's active wallet and MPIN
		try:
			self.wallet = Wallet.objects.get(user=user, status='ACTIVE')
			# !! SECURITY WARNING: Assumes self.wallet.mpin is appropriately handled (e.g., hashed) !!
			if not self.wallet.mpin:
				raise serializers.ValidationError("MPIN is not set for your wallet. Please set it first.")
			# Direct comparison:
			if mpin != self.wallet.mpin:
				raise serializers.ValidationError("Invalid MPIN.")
		except Wallet.DoesNotExist:
			raise serializers.ValidationError("No active wallet found for your account.")
		except Wallet.MultipleObjectsReturned:
			self.wallet = Wallet.objects.filter(user=user, status='ACTIVE').first()
			if not self.wallet:
				raise serializers.ValidationError("No active wallet found for your account.")
			# Repeat MPIN check with direct comparison
			# !! SECURITY WARNING: Assumes self.wallet.mpin is appropriately handled (e.g., hashed) !!
			if not self.wallet.mpin:
				raise serializers.ValidationError("MPIN is not set for your wallet. Please set it first.")
			# Direct comparison:
			if mpin != self.wallet.mpin:
				raise serializers.ValidationError("Invalid MPIN.")
		
		# Check if amount exceeds available balance (consider fees later if applicable)
		if data['amount'] > self.wallet.available_balance:
			raise serializers.ValidationError(f"Insufficient balance. Available: {self.wallet.available_balance}")
		
		# Basic phone number validation (you might want more specific validation)
		phone_number = data.get('phone_number')
		if not phone_number or not phone_number.isdigit():
			raise serializers.ValidationError("Invalid phone number format.")
		# Prevent sending to self
		if phone_number == user.mobile:  # Assuming user model has a 'mobile' field
			raise serializers.ValidationError("Cannot send funds to your own phone number.")
		
		return data


class UpdateMpinSerializer(serializers.Serializer):
	wallet_id = serializers.IntegerField()
	current_mpin = serializers.CharField(required=False, allow_blank=True, 
										min_length=4, max_length=4, 
										validators=[RegexValidator(regex=r'^\d{4}$', 
													  message="MPIN must be exactly 4 digits.")])
	new_mpin = serializers.CharField(min_length=4, max_length=4, 
									validators=[RegexValidator(regex=r'^\d{4}$', 
												  message="MPIN must be exactly 4 digits.")])
	confirm_mpin = serializers.CharField(min_length=4, max_length=4)
	
	def validate(self, data):
		# Check that new_mpin and confirm_mpin match
		if data.get('new_mpin') != data.get('confirm_mpin'):
			raise serializers.ValidationError({"confirm_mpin": "Confirmation MPIN doesn't match new MPIN"})
		
		# Validate the wallet belongs to the user
		wallet_id = data.get('wallet_id')
		try:
			wallet = Wallet.objects.get(wallet_id=wallet_id)
			
			# Only check the current_mpin if the wallet already has an MPIN set
			# If wallet.mpin is None or empty, no need to validate current_mpin
			if wallet.mpin:
				if not data.get('current_mpin'):
					raise serializers.ValidationError({"current_mpin": "Current MPIN is required"})
				if wallet.mpin != data.get('current_mpin'):
					raise serializers.ValidationError({"current_mpin": "Current MPIN is incorrect"})
		except Wallet.DoesNotExist:
			raise serializers.ValidationError({"wallet_id": "Wallet not found"})
			
		return data


class WithdrawalFeeRequestSerializer(serializers.Serializer):
	amount = serializers.DecimalField(max_digits=20, decimal_places=2, min_value=1)
	withdrawal_type = serializers.CharField(default="KE_DTB_MPESA", required=False)
	
	def validate_amount(self, value):
		if value <= 0:
			raise serializers.ValidationError("Amount must be greater than 0")
		return value


class WithdrawalFeeResponseSerializer(serializers.Serializer):
	fee_amount = serializers.DecimalField(max_digits=20, decimal_places=2, source="feeAmount")


class CheckContactWalletRequestSerializer(serializers.Serializer):
	phone_number = serializers.CharField(max_length=20, required=True)
	name = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
	
	def validate_phone_number(self, value):
		# Add more specific validation if needed (e.g., regex for Kenyan numbers)
		if not value or not value.isdigit():
			raise serializers.ValidationError("Invalid phone number format.")
		# You might want to prevent checking the user's own number
		request = self.context.get('request')
		if request and request.user and value == request.user.mobile:
			raise serializers.ValidationError("Cannot check your own phone number.")
		return value


class UserContactSerializer(serializers.ModelSerializer):
	class Meta:
		model = UserContact
		fields = ['id', 'name', 'phone_number', 'last_used']
		read_only_fields = ['id', 'last_used']


class BankBeneficiarySerializer(serializers.ModelSerializer):
	"""Serializer for bank beneficiary management."""
	
	class Meta:
		model = BankBeneficiary
		fields = [
			'id', 'account_holder_name', 'account_number', 'bank_code', 
			'branch_code', 'bank_name', 'branch_name', 'nickname', 
			'is_active', 'created_at', 'updated_at', 'last_used'
		]
		read_only_fields = ['id', 'created_at', 'updated_at', 'last_used']
	
	def validate(self, data):
		# Ensure the beneficiary belongs to the requesting user
		request = self.context.get('request')
		if request and request.user:
			# Check for duplicate account for the same user
			user = request.user
			account_number = data.get('account_number')
			bank_code = data.get('bank_code')
			
			# For updates, exclude the current instance
			queryset = BankBeneficiary.objects.filter(
				user=user, 
				account_number=account_number, 
				bank_code=bank_code
			)
			if self.instance:
				queryset = queryset.exclude(id=self.instance.id)
			
			if queryset.exists():
				raise serializers.ValidationError(
					"You already have this bank account as a beneficiary."
				)
		
		return data


class CreateBankBeneficiarySerializer(serializers.ModelSerializer):
	"""Serializer for creating new bank beneficiaries."""
	
	class Meta:
		model = BankBeneficiary
		fields = [
			'account_holder_name', 'account_number', 'bank_code', 
			'branch_code', 'bank_name', 'branch_name', 'nickname'
		]
	
	def validate_account_number(self, value):
		if not value or not value.isdigit():
			raise serializers.ValidationError("Account number must contain only digits.")
		if len(value) < 8 or len(value) > 20:
			raise serializers.ValidationError("Account number must be between 8 and 20 digits.")
		return value
	
	def validate_bank_code(self, value):
		if not value or not value.isdigit():
			raise serializers.ValidationError("Bank code must contain only digits.")
		return value
	
	def validate_branch_code(self, value):
		if not value or not value.isdigit():
			raise serializers.ValidationError("Branch code must contain only digits.")
		return value


class WalletToBankTransferSerializer(serializers.Serializer):
	"""Serializer for wallet to bank transfers (both PesaLink and EFT)."""
	
	TRANSFER_TYPES = [
		('PESALINK', 'PesaLink Transfer'),
		('EFT', 'Electronic Funds Transfer'),
	]
	
	beneficiary_id = serializers.IntegerField(help_text="ID of the bank beneficiary")
	amount = serializers.DecimalField(
		max_digits=20, decimal_places=2, min_value=1, max_value=1000000
	)
	transfer_type = serializers.ChoiceField(choices=TRANSFER_TYPES)
	description = serializers.CharField(max_length=200, required=False, allow_blank=True)
	reference = serializers.CharField(max_length=100, required=False, allow_blank=True)
	mpin = serializers.CharField(write_only=True, min_length=4, max_length=6)
	
	def validate(self, data):
		request = self.context.get('request')
		if not request or not request.user:
			raise serializers.ValidationError("User context is required.")
		
		user = request.user
		mpin = data.get('mpin')
		beneficiary_id = data.get('beneficiary_id')
		
		# Validate user's active wallet and MPIN
		try:
			self.wallet = Wallet.objects.get(user=user, status='ACTIVE')
			if not self.wallet.mpin:
				raise serializers.ValidationError("MPIN is not set for your wallet. Please set it first.")
			if mpin != self.wallet.mpin:
				raise serializers.ValidationError("Invalid MPIN.")
		except Wallet.DoesNotExist:
			raise serializers.ValidationError("No active wallet found for your account.")
		except Wallet.MultipleObjectsReturned:
			self.wallet = Wallet.objects.filter(user=user, status='ACTIVE').first()
			if not self.wallet:
				raise serializers.ValidationError("No active wallet found for your account.")
			if not self.wallet.mpin:
				raise serializers.ValidationError("MPIN is not set for your wallet. Please set it first.")
			if mpin != self.wallet.mpin:
				raise serializers.ValidationError("Invalid MPIN.")
		
		# Validate beneficiary belongs to user and is active
		try:
			self.beneficiary = BankBeneficiary.objects.get(
				id=beneficiary_id, user=user, is_active=True
			)
		except BankBeneficiary.DoesNotExist:
			raise serializers.ValidationError("Invalid beneficiary or beneficiary not found.")
		
		# Check if amount exceeds available balance
		if data['amount'] > self.wallet.available_balance:
			raise serializers.ValidationError(
				f"Insufficient balance. Available: {self.wallet.available_balance}"
			)
		
		# Set minimum amounts based on transfer type
		if data['transfer_type'] == 'PESALINK' and data['amount'] < 10:
			raise serializers.ValidationError("Minimum amount for PesaLink transfer is KES 10.")
		elif data['transfer_type'] == 'EFT' and data['amount'] < 100:
			raise serializers.ValidationError("Minimum amount for EFT transfer is KES 100.")
		
		return data


class BankTransferFeeRequestSerializer(serializers.Serializer):
	"""Serializer for requesting bank transfer fees."""
	
	TRANSFER_TYPES = [
		('PESALINK', 'PesaLink Transfer'),
		('EFT', 'Electronic Funds Transfer'),
	]
	
	amount = serializers.DecimalField(max_digits=20, decimal_places=2, min_value=1)
	transfer_type = serializers.ChoiceField(choices=TRANSFER_TYPES)
	
	def validate_amount(self, value):
		if value <= 0:
			raise serializers.ValidationError("Amount must be greater than 0")
		return value


class BankTransferFeeResponseSerializer(serializers.Serializer):
	"""Serializer for bank transfer fee responses."""
	fee_amount = serializers.DecimalField(max_digits=20, decimal_places=2, source="feeAmount")
	transfer_type = serializers.CharField()
