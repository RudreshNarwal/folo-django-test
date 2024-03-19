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
from core_apps.users.serializers.auth import VerifyOTPRequestSerializer
from django.contrib.auth import get_user_model
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated

from ..serializers.user import UserSerializer

class UserView(viewsets.ViewSet):
    model = User
    permission_classes = (IsAuthenticated,)
    serializer_class = UserSerializer
    
    # def get_object(self):
    #     return self.request.user
    # def get_queryset(self):
    #     return self.model.objects.all()
    
    @action(methods=['GET'], detail=False)
    def me(self, request):
        user=request.user
        # user = self.get_queryset().filter().first()
        serializer = UserSerializer(instance=user)
        return response.Response(serializer.data)
    
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def register(self, request):
        serializer = UserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        mobile = serializer.validated_data.get('mobile')
        
        if mobile and User.objects.filter(mobile=mobile).exists():
            return response.Response({
                "message": "User already registered."
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if serializer.is_valid():
            user = serializer.save()
            return response.Response({
                "user": UserSerializer(user).data,
                "message": "User successfully registered."
            }, status=status.HTTP_201_CREATED)
        else:
            return response.Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# class CustomUserDetailsView(RetrieveUpdateAPIView):
#     serializer_class = UserSerializer
#     permission_classes = (IsAuthenticated,)
#     model = User
#
#     def get_object(self):
#         return self.request.user
#
#     def get_queryset(self):
#         return self.model.objects.all().filter().first()
