from django.utils.timezone import now, timedelta

from core_apps.payments.models import Subscription


def create_subscription(transaction):
	# Check if a subscription already exists for this transaction
	if Subscription.objects.filter(transaction=transaction).exists():
		# A subscription already exists for this transaction, so don't create or update
		return None, False
	
	# If no subscription exists for the transaction, proceed to create one
	duration_days = transaction.plan.duration_days or 30  # Default to 30 days if not specified
	# Calculate start and end dates
	start_date = now().date()
	end_date = start_date + timedelta(days=duration_days)
	
	# Create the subscription
	subscription = Subscription.objects.create(
		user=transaction.user,
		plan=transaction.plan,
		start_date=start_date,
		end_date=end_date,
		is_active=True,
		amount_paid=transaction.amount,  # Assuming you add amount_paid to the Subscription model
		transaction=transaction  # Link the subscription to the transaction
	)
	
	return subscription, True
