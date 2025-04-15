from django.core.validators import RegexValidator
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django_countries.serializers import CountryFieldMixin
from .models import CustomerProfile, ProviderDocument, TopUpTransaction, Transaction, Wallet

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
	from_wallet_number = serializers.CharField(source='from_wallet.account_number', read_only=True)
	to_wallet_number = serializers.CharField(source='to_wallet.account_number', read_only=True, allow_null=True)
	
	class Meta:
		model = Transaction
		fields = [
			'transaction_id', 'transaction_type', 'amount', 'fee',
			'from_wallet_number', 'to_wallet_number', 'to_wallet_id',
			'currency', 'status', 'description', 'gateway',
			'gateway_transaction_id', 'deliver_to_phone',
			'reference', 'created_at', 'updated_at',
		]
		read_only_fields = [
			'transaction_id', 'fee', 'status', 'gateway',
			'gateway_transaction_id', 'created_at', 'updated_at',
		]


class WalletToWalletTransferSerializer(serializers.Serializer):
	amount = serializers.DecimalField(max_digits=20, decimal_places=2, min_value=1)
	description = serializers.CharField(required=False, allow_blank=True)
	from_wallet_id = serializers.IntegerField()
	to_wallet_id = serializers.IntegerField()
	mpin = serializers.CharField(write_only=True, min_length=4, max_length=6)
	
	def validate_amount(self, value):
		if value <= 0:
			raise serializers.ValidationError("Amount must be greater than 0")
		return value
	
	def validate_from_wallet_id(self, value):
		try:
			wallet = Wallet.objects.get(wallet_id=value)
			if wallet.status != 'ACTIVE':
				raise serializers.ValidationError("Source wallet is not active")
		except Wallet.DoesNotExist:
			raise serializers.ValidationError("Source wallet not found")
		return value
	
	def validate(self, data):
		# Validate MPIN for from_wallet
		try:
			wallet = Wallet.objects.get(wallet_id=data['from_wallet_id'])
			if wallet.mpin != data['mpin']:
				raise serializers.ValidationError({"mpin": "Invalid MPIN"})
			
			# Check if wallet has sufficient balance
			if wallet.available_balance < data['amount']:
				raise serializers.ValidationError({"amount": "Insufficient balance in wallet"})
		
		except Wallet.DoesNotExist:
			raise serializers.ValidationError({"from_wallet_id": "Source wallet not found"})
		
		return data


class WalletToMpesaTransferSerializer(serializers.Serializer):
	wallet_id = serializers.IntegerField()
	amount = serializers.DecimalField(max_digits=20, decimal_places=2, min_value=1)
	deliver_to_phone = serializers.CharField()
	reference = serializers.CharField(required=False)
	description = serializers.CharField(required=False, allow_blank=True)
	mpin = serializers.CharField(write_only=True, min_length=4, max_length=6)
	
	def validate_wallet_id(self, value):
		try:
			wallet = Wallet.objects.get(wallet_id=value)
			if wallet.status != 'ACTIVE':
				raise serializers.ValidationError("Wallet is not active")
		except Wallet.DoesNotExist:
			raise serializers.ValidationError("Wallet not found")
		return value
	
	def validate_deliver_to_phone(self, value):
		# Simple validation for phone number format
		if not value.isdigit() or not value.startswith('254'):
			raise serializers.ValidationError("Phone number should be in format 254XXXXXXXXX")
		return value
	
	def validate(self, data):
		# Validate MPIN
		try:
			wallet = Wallet.objects.get(wallet_id=data['wallet_id'])
			if wallet.mpin != data['mpin']:
				raise serializers.ValidationError({"mpin": "Invalid MPIN"})
			
			# Check if wallet has sufficient balance
			if wallet.available_balance < data['amount']:
				raise serializers.ValidationError({"amount": "Insufficient balance in wallet"})
		
		except Wallet.DoesNotExist:
			raise serializers.ValidationError({"wallet_id": "Wallet not found"})
		
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
