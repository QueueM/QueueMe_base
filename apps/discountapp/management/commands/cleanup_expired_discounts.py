# apps/discountapp/management/commands/cleanup_expired_discounts.py
import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.discountapp.models import Coupon, ServiceDiscount


class Command(BaseCommand):
    help = "Clean up expired discounts and coupons"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Number of days after expiry to consider for cleanup",
        )
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Actually delete the records (default is to only report)",
        )

    def handle(self, *args, **options):
        days = options["days"]
        delete = options["delete"]

        now = timezone.now()
        cleanup_threshold = now - datetime.timedelta(days=days)

        # Find long-expired discounts
        old_discounts = ServiceDiscount.objects.filter(
            status="expired", end_date__lt=cleanup_threshold
        )

        # Find long-expired coupons
        old_coupons = Coupon.objects.filter(status="expired", end_date__lt=cleanup_threshold)

        self.stdout.write(
            self.style.SUCCESS(
                f"Found {old_discounts.count()} expired discounts older than {days} days"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Found {old_coupons.count()} expired coupons older than {days} days"
            )
        )

        if delete:
            # Delete records
            discount_count = old_discounts.count()
            old_discounts.delete()

            coupon_count = old_coupons.count()
            old_coupons.delete()

            self.stdout.write(self.style.SUCCESS(f"Deleted {discount_count} expired discounts"))
            self.stdout.write(self.style.SUCCESS(f"Deleted {coupon_count} expired coupons"))
        else:
            self.stdout.write(
                self.style.WARNING(
                    "Records were not deleted. Use --delete flag to actually delete records"
                )
            )
