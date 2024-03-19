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

class IsOwnerOrReadOnly(IsAuthenticated):
    # Custom permission to only allow owners of an object to edit it. Assumes the model instance has an `owner` attribute.
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request, so we'll always allow GET, HEAD or OPTIONS requests.
        # if request.method in ('GET', 'HEAD', 'OPTIONS'):
        #     return True
        
        # Write permissions are only allowed to the owner of the user profile.
        return obj == request.user


class UserViewSet(viewsets.ModelViewSet):
    #A viewset for viewing and editing the logged in user's profile.
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsOwnerOrReadOnly]

    def get_object(self):
       #Overrides the default method to return the user profile for the logged in user.
        # Ensure the user is trying to get or update their own profile
        # This is useful for URLs like /api/users/me/ where `me` can be used
        # as a keyword to get the logged-in user's profile.
        if self.kwargs.get('pk', None) == 'me':
            return self.request.user
        return super(UserViewSet, self).get_object()
    
    def partial_update(self, request, *args, **kwargs):
        # Custom update method to handle user profile updates.
        instance = self.get_object()
        # Prevent users from updating other users' profiles
        if instance != request.user:
            return Response({'message': 'You do not have permission to update this user.'},
                            status=status.HTTP_403_FORBIDDEN)
        
        serializer = self.get_serializer(instance, data=request.data, partial=kwargs.pop('partial', True))
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return Response(serializer.data)
    
    @action(methods=['GET'], detail=False)
    def me(self, request):
        user = request.user
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
    
    def update(self, request, *args, **kwargs):
        # Disable the partial update (PUT) action.
        return Response({'message': 'PUT method is not allowed.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
    
    def list(self, request, *args, **kwargs):
        # Disable the partial update (PATCH) action.
        return Response({'message': 'GET list method is not allowed.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
    
    def destroy(self, request, *args, **kwargs):
        #Disable the destroy (DELETE) action.
        return Response({'message': 'DELETE method is not allowed.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

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
        user = request.user
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
