# apps/discountapp/management/commands/generate_coupons.py
import datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.categoriesapp.models import Category
from apps.discountapp.services.coupon_service import CouponService
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop


class Command(BaseCommand):
    help = "Generate coupons for a shop"

    def add_arguments(self, parser):
        parser.add_argument("shop_id", type=str, help="ID of the shop")
        parser.add_argument("--name", type=str, default="Generated Coupon", help="Coupon name")
        parser.add_argument(
            "--discount-type",
            type=str,
            choices=["percentage", "fixed"],
            default="percentage",
            help="Discount type",
        )
        parser.add_argument("--value", type=float, required=True, help="Discount value")
        parser.add_argument("--duration", type=int, default=30, help="Duration in days")
        parser.add_argument("--quantity", type=int, default=1, help="Number of coupons to generate")
        parser.add_argument("--usage-limit", type=int, default=1, help="Usage limit per coupon")
        parser.add_argument(
            "--service-ids", type=str, nargs="*", help="Service IDs to apply coupon to"
        )
        parser.add_argument(
            "--category-ids",
            type=str,
            nargs="*",
            help="Category IDs to apply coupon to",
        )
        parser.add_argument("--all-services", action="store_true", help="Apply to all services")

    def handle(self, *args, **options):
        shop_id = options["shop_id"]
        name = options["name"]
        discount_type = options["discount_type"]
        value = options["value"]
        duration = options["duration"]
        quantity = options["quantity"]
        usage_limit = options["usage_limit"]
        service_ids = options["service_ids"] or []
        category_ids = options["category_ids"] or []
        apply_to_all_services = options["all_services"]

        try:
            # Get shop
            shop = Shop.objects.get(id=shop_id)

            # Get services if provided
            services = None
            if service_ids:
                services = Service.objects.filter(id__in=service_ids)
                if not services.exists():
                    raise CommandError("No services found with the provided IDs")

            # Get categories if provided
            categories = None
            if category_ids:
                categories = Category.objects.filter(id__in=category_ids)
                if not categories.exists():
                    raise CommandError("No categories found with the provided IDs")

            # Set dates
            now = timezone.now()
            end_date = now + datetime.timedelta(days=duration)

            # Generate coupons
            if quantity == 1:
                # Generate single coupon
                coupon = CouponService.create_coupon(
                    shop=shop,
                    name=name,
                    discount_type=discount_type,
                    value=value,
                    start_date=now,
                    end_date=end_date,
                    usage_limit=usage_limit,
                    is_single_use=(usage_limit == 1),
                    apply_to_all_services=apply_to_all_services,
                    services=services,
                    categories=categories,
                )

                self.stdout.write(
                    self.style.SUCCESS(f"Created coupon: {coupon.code} - {coupon.name}")
                )
            else:
                # Generate bulk coupons
                coupons = CouponService.generate_bulk_coupons(
                    shop=shop,
                    name_template=f"{name} {{i}}",
                    discount_type=discount_type,
                    value=value,
                    start_date=now,
                    end_date=end_date,
                    quantity=quantity,
                    usage_limit=usage_limit,
                    is_single_use=(usage_limit == 1),
                    apply_to_all_services=apply_to_all_services,
                    services=services,
                    categories=categories,
                )

                self.stdout.write(self.style.SUCCESS(f"Created {len(coupons)} coupons"))

                for coupon in coupons:
                    self.stdout.write(f"  {coupon.code}")

        except Shop.DoesNotExist:
            raise CommandError(f"Shop with ID {shop_id} does not exist")
