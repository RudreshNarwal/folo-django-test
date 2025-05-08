from django.core.validators import RegexValidator
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django_countries.serializers import CountryFieldMixin
from .models import CustomerProfile, ProviderDocument, TopUpTransaction, Transaction, Wallet, UserContact, WalletType

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
	
	class Meta:
		model = Transaction
		fields = [
			'transaction_id', 'transaction_type', 'amount', 'fee', 'currency',
			'status', 'description', 'created_at', 'from_wallet_id',
			'to_wallet_id', 'deliver_to_phone', 'gateway_transaction_id',
			'contact_name', 'contact_phone'
		]
		read_only_fields = fields


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
