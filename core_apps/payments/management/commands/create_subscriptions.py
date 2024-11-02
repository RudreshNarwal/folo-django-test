from django.core.management.base import BaseCommand
from django.utils import timezone
from core_apps.payments.models import Subscription, Transaction
from core_apps.users.models import User


#### Script to run this command #####
#python manage.py create_subscriptions <mobile_number>
# docker compose -f production.yml run --rm api python manage.py create_subscriptions <mobile_number>
#python manage.py create_subscriptions 725763465

class Command(BaseCommand):
    help = 'Create subscriptions for users who have made successful payments but do not have active subscriptions.'

    def add_arguments(self, parser):
        parser.add_argument('mobile', type=str, help='The mobile number of the user to process.')

    def handle(self, *args, **options):
        mobile_number = options['mobile']

        # Get the user by mobile number
        try:
            user = User.objects.get(mobile=mobile_number)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"User with mobile number {mobile_number} does not exist."))
            return

        # Check if the user has a successful transaction without a subscription
        successful_transactions = Transaction.objects.filter(
            user=user,
            status='Successful',
            subscription__isnull=True  # Ensure there's no existing subscription for this transaction
        )

        if not successful_transactions.exists():
            self.stdout.write(self.style.WARNING(f"No successful transactions found for user with mobile number {mobile_number}."))
            return

        for transaction in successful_transactions:
            # Check if there's already a subscription created for this transaction
            existing_subscription = Subscription.objects.filter(
                transaction=transaction
            ).exists()
            
            if existing_subscription:
                self.stdout.write(self.style.WARNING(f"Subscription already exists for transaction {transaction.id}. Skipping creation."))
                continue
            
            # Check if the user already has an active subscription for this plan
            if not Subscription.objects.filter(user=user, plan=transaction.plan, is_active=True).exists():
                # Create the subscription
                subscription = Subscription.objects.create(
                    user=user,
                    plan=transaction.plan,
                    start_date=timezone.now().date(),
                    end_date=timezone.now().date() + timezone.timedelta(days=transaction.plan.duration_days),
                    is_active=True,
                    autopay=False,
                    amount_paid=transaction.amount,
                    transaction=transaction,
                )

                # Check that the subscription matches the transaction values
                if (subscription.amount_paid == transaction.amount and
                    subscription.plan == transaction.plan and
                    subscription.user == transaction.user):
                    self.stdout.write(self.style.SUCCESS(f"Subscription created successfully for mobile {mobile_number} with matching values."))
                else:
                    self.stdout.write(self.style.ERROR(f"Subscription created for mobile {mobile_number}, but values do not match the transaction."))
            else:
                self.stdout.write(self.style.WARNING(f"User with mobile number {mobile_number} already has an active subscription for this plan."))


# Explanation:
# add_arguments Method: Adds an argument for the mobile number, which you will pass when running the script.
# handle Method:
# Retrieves the user based on the provided mobile number.
# Checks for any successful transactions that do not have a subscription linked.
# If no active subscription exists for the user's plan, it creates one.
# After creating the subscription, it verifies that the amount_paid, plan, and user match between the subscription and the transaction.
# Outputs the result of each operation, whether success, warning, or error.
# Integration with Production:
# Automation: You can schedule this command to run periodically using cron jobs or a task scheduler to ensure that any successful payments without corresponding subscriptions are handled automatically.
# Logging: Ensure that you have appropriate logging or notifications set up in production to monitor the success and failure of this command.