from django import forms
from django.contrib.auth import forms as admin_forms
from django.contrib.auth import get_user_model

User = get_user_model()


class UserChangeForm(admin_forms.UserChangeForm):
	class Meta(admin_forms.UserChangeForm.Meta):
		model = User


class UserCreationForm(admin_forms.UserCreationForm):
	class Meta(admin_forms.UserCreationForm.Meta):
		model = User
		fields = ("first_name", "last_name", "email", "mobile")
	
	error_messages = {
		"duplicate_email": "A user with this email already exists.",
		"duplicate_mobile": "A user with this mobile already exists.",
	}
	
	def clean_email(self):  # overriding with clean_email method
		email = self.cleaned_data["email"]
		try:
			User.objects.get(email=email)
		except User.DoesNotExist:
			return email
		raise forms.ValidationError(self.error_messages["duplicate_email"])
	
	def clean_mobile(self):
		mobile = self.cleaned_data["mobile"]
		try:
			User.objects.get(mobile=mobile)
		except User.DoesNotExist:
			return mobile
		raise forms.ValidationError(self.error_messages["duplicate_mobile"])
