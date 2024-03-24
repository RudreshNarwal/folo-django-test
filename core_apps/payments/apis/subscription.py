from django.utils.timezone import now
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from core_apps.payments.serializers.subscription import SubscriptionSerializer
from ..models import Subscription


class ActiveSubscriptionAPIView(APIView):
	permission_classes = [IsAuthenticated]
	
	def deactivate_expired_subscriptions(self, user):
		"""Deactivate expired subscriptions for the user."""
		Subscription.objects.filter(user=user, end_date__lt=now(), is_active=True).update(is_active=False)
	
	def get(self, request, *args, **kwargs):
		# First, deactivate expired subscriptions
		self.deactivate_expired_subscriptions(request.user)
		
		# Then, fetch the user's active subscriptions
		active_subscriptions = Subscription.objects.filter(user=request.user, is_active=True)
		serializer = SubscriptionSerializer(active_subscriptions, many=True)
		return Response(serializer.data)
