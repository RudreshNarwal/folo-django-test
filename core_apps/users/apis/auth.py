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
from core_apps.users.serializers.user import RegisterUserMobileSerializer
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
        
        # Now, you can use the mobile and country_code variables to look up the user
        user = self.model.objects.filter(mobile=mobile, country_code=country_code).first()

        if user is not None:
            otp = user.send_otp()
            return Response({
                "message": "Otp sent successfully !!"
            }, status=status.HTTP_200_OK)

        if user is None:
            serializer = RegisterUserMobileSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user = serializer.save()
            otp = user.send_otp()
            return Response({
                "message": "Otp sent successfully !!"
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

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