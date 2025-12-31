from django import forms


class MobileLoginForm(forms.Form):
    """Form for entering mobile number to receive OTP."""
    country_code = forms.CharField(
        max_length=5,
        initial='+254',
        widget=forms.TextInput(attrs={
            'class': 'w-24 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': '+254'
        })
    )
    mobile = forms.CharField(
        max_length=15,
        min_length=5,
        widget=forms.TextInput(attrs={
            'class': 'flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Enter mobile number',
            'autofocus': True
        })
    )


class OTPVerifyForm(forms.Form):
    """Form for entering OTP."""
    otp = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 text-center text-2xl tracking-widest border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': '000000',
            'maxlength': '6',
            'autofocus': True
        })
    )
