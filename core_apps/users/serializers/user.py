from rest_framework import serializers

from core_apps.users.models import User
from django_countries.serializer_fields import CountryField
from phonenumber_field.serializerfields import PhoneNumberField
from rest_framework import serializers



class RegisterUserMobileSerializer(serializers.ModelSerializer):
    mobile = serializers.CharField(required=True, max_length=15, min_length=5)

    class Meta:
        model = User
        fields = ["mobile", ]


class UserSerializer(serializers.ModelSerializer):
    mobile = serializers.CharField(required=True, max_length=15, min_length=5)
    nation_id = serializers.CharField(required=True, max_length=20)
    first_name = serializers.CharField(required=True, max_length=128)
    middle_name = serializers.CharField(required=False, max_length=128, allow_null=True, allow_blank=True)
    last_name = serializers.CharField(required=False, max_length=128, allow_null=True, allow_blank=True)
    email=serializers.EmailField(required=True)
    dob = serializers.DateField(required=True)
    class Meta:
        model = User
        fields = [
            'pkid', 'id', 'first_name', 'middle_name', 'last_name', "dob", "mobile",
            'is_mobile_verified', 'email', "gender", "nation_id", "is_email_verified"
        ]


# Other

# class UserSerializer(serializers.ModelSerializer):
#     gender = serializers.CharField(source="profile.gender")  # profile is related_name in profile model used to access profile datd
#     phone_number = PhoneNumberField(source="profile.phone_number")
#     profile_photo = serializers.ReadOnlyField(source="profile.profile_photo.url")
#     country = CountryField(source="profile.country")
#     city = serializers.CharField(source="profile.city")
#
#     class Meta:
#         model = AuthUser
#         fields = [
#             "id",
#             "email",
#             "first_name",
#             "last_name",
#             "gender",
#             "phone_number",
#             "profile_photo",
#             "country",
#             "city",
#         ]
#
#     def to_representation(self,
#                           instance):  # representation method -> to add the admin field to the serialized data, and it will only show the admin fields if and only if the user is an admin.
#         representation = super(UserSerializer, self).to_representation(instance)
#         if instance.is_superuser:
#             representation["admin"] = True
#         return representation
#
#
# class CustomRegisterSerializer(RegisterSerializer):
#     username = None
#     first_name = serializers.CharField(required=True)
#     last_name = serializers.CharField(required=True)
#     email = serializers.EmailField(required=True)
#     mobile = serializers.CharField(required=True)
#     password1 = serializers.CharField(write_only=True)
#     password2 = serializers.CharField(write_only=True)
#
#     def get_cleaned_data(self):
#         super().get_cleaned_data()
#         return {
#             "email": self.validated_data.get("email", ""),
#             "mobile": self.validated_data.get("mobile", ""),
#             "first_name": self.validated_data.get("first_name", ""),
#             "last_name": self.validated_data.get("last_name", ""),
#             "password1": self.validated_data.get("password1", ""),
#         }
#
#     def save(self, request):
#         adapter = get_adapter()
#         user = adapter.new_user(request)
#         self.cleaned_data = self.get_cleaned_data()
#         user = adapter.save_user(request, user, self)
#         user.save()
#
#         setup_user_email(request, user, [])
#         user.email = self.cleaned_data.get("email")
#         user.mobile = self.cleaned_data.get("mobile")
#         user.password = self.cleaned_data.get("password1")
#         user.first_name = self.cleaned_data.get("first_name")
#         user.last_name = self.cleaned_data.get("last_name")
#
#         return user