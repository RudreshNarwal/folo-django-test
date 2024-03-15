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
from core_apps.users.serializers.user import RegisterUserSerializer
from core_apps.users.serializers.auth import VerifyOTPRequestSerializer
from django.contrib.auth import get_user_model
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated

from ..serializers.user import UserSerializer

class UserView(viewsets.ViewSet):
    model = User
    permission_classes = [AllowAny]
    serializer_class = RegisterUserSerializer

    def get_queryset(self):
        return self.model.objects.all()

    @action(methods=['POST'], detail=False)
    def send_otp(self, request):

        serializer = RegisterUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = self.model.objects.filter(mobile=serializer.validated_data.get('mobile')).first()

        if user is not None:
            otp = user.send_otp()
            return Response({
                "otp": otp,
                "message": "Otp sent successfully !!"
            }, status=status.HTTP_200_OK)

        if user is None:
            serializer = RegisterUserSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user = serializer.save()
            otp = user.send_otp()
            return Response({
                "otp": otp,
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

    # @action(methods=['GET'], detail=False)
    # def me(self, request):
    #     user = self.get_queryset().filter().first()
    #     serializer = UserSerializer(instance=user)
    #     return response.Response(serializer.data)
    #     pass
    
class CustomUserDetailsView(RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        return self.request.user

    def get_queryset(self):
        return get_user_model().objects.none()