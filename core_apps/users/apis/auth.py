from __future__ import unicode_literals

import json
import requests
from rest_framework import status, response
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from core_apps.users.models.user import User
from core_apps.users.serializers.auth import RegisterUserMobileSerializer
from core_apps.users.serializers.auth import VerifyOTPRequestSerializer
from django.contrib.auth import get_user_model
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated

from ..serializers.user import UserSerializer


class AuthView(viewsets.ViewSet):
    model = User
    permission_classes = [AllowAny]
    serializer_class = RegisterUserMobileSerializer

    def get_queryset(self):
        return self.model.objects.all()

    @action(methods=['POST'], detail=False)
    def send_otp(self, request):
        serializer = RegisterUserMobileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        mobile = serializer.validated_data.get('mobile')
        country_code = serializer.validated_data.get('country_code')

        user = self.model.objects.filter(mobile=mobile).first()

        if user:
            # If user exists, update country code if necessary and send OTP
            if user.country_code != country_code:
                user.country_code = country_code
                user.save(update_fields=['country_code'])

            otp = user.send_otp()
            return Response({
                "is_registered": user.email is not None and user.email.strip() != "",
                "message": "Otp sent successfully !!"
            }, status=status.HTTP_200_OK)
        else:
            # If user does not exist, create a new one and send OTP
            user = serializer.save()
            otp = user.send_otp()
            return Response({
                "is_registered": user.email is not None and user.email.strip() != "",
                "message": "Otp sent successfully !!"
            }, status=status.HTTP_201_CREATED)

    @action(methods=['POST'], detail=False)
    def verify_otp(self, request):

        serializer = VerifyOTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        otp = serializer.validated_data['otp'] if 'otp' in serializer.validated_data else None
        user = self.model.objects.filter(mobile=serializer.validated_data['mobile']).first()

        if not user:
            raise AuthenticationFailed('User does not exist.')

        is_verified = user.verify_otp(supplied_otp=otp)
        if not is_verified:
            error_message = "Please enter valid otp !!"
            return Response(
                {"message": error_message},
                status=status.HTTP_400_BAD_REQUEST
            )

        response = Response()
        refresh = RefreshToken.for_user(user)
        response.data = {
            "status": "success",
            "jwt": str(refresh.access_token)
        }
        return response
