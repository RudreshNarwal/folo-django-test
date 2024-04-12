from django.utils.timezone import now
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from core_apps.payments.serializers.subscription import PlanSerializer, SubscriptionSerializer
from generics.utils.deactivate_expired_subscriptions import deactivate_expired_subscriptions
from ..models import Subscription, Plan


class ActiveSubscriptionAPIView(APIView):
	permission_classes = [IsAuthenticated]
	
	
	def get(self, request, *args, **kwargs):
		# First, deactivate expired subscriptions
		deactivate_expired_subscriptions(request.user)
		
		# Then, fetch the user's active subscriptions
		active_subscriptions = Subscription.objects.filter(user=request.user, is_active=True)
		serializer = SubscriptionSerializer(active_subscriptions, many=True)
		return Response(serializer.data)
	
class PlanAPIView(APIView):
	permission_classes = [IsAuthenticated]
	
	def get(self, request, *args, **kwargs):
		# First, deactivate expired subscriptions
		deactivate_expired_subscriptions(request.user)
		
		active_subscriptions = Plan.objects.filter(is_active=True)
		serializer = PlanSerializer(active_subscriptions, many=True)
		return Response(serializer.data)
