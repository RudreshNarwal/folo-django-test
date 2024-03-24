from django.utils.timezone import now, timedelta

from core_apps.payments.models import Subscription


def create_subscription(self, transaction):
	# Determine subscription duration
	duration_days = transaction.plan.duration_days or 30  # Default to 30 days
	
	# Calculate start and end dates
	start_date = now().date()
	end_date = start_date + timedelta(days=duration_days)
	
	# Create the subscription
	Subscription.objects.create(
		user=transaction.user,
		plan=transaction.plan,
		start_date=start_date,
		end_date=end_date,
		is_active=True,
		# Assuming autopay or other relevant fields are handled elsewhere or set to default
	)
