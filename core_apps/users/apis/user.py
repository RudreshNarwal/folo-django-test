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
    
    @action(detail=False, methods=['post'])
    def register(self, request, *args, **kwargs):
        # Check if the user already exists
        if request.user.email is not None:
            return response.Response({
                "message": "User already registered."
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = self.get_serializer(request.user, data=request.data, partial=kwargs.pop('partial', True))
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        # Return the newly registered user's data
        return response.Response({
            "user": serializer.data,
            "message": "User successfully registered."
        }, status=status.HTTP_201_CREATED)
    
    def update(self, request, *args, **kwargs):
        # Disable the partial update (PUT) action.
        return Response({'message': 'PUT method is not allowed.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
    
    def list(self, request, *args, **kwargs):
        # Disable the partial update (PATCH) action.
        return Response({'message': 'GET list method is not allowed.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
    
    def destroy(self, request, *args, **kwargs):
        #Disable the destroy (DELETE) action.
        return Response({'message': 'DELETE method is not allowed.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)



