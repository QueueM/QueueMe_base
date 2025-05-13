from django.db import transaction
from django.utils import timezone

from apps.authapp.models import User
from apps.employeeapp.models import Employee
from apps.geoapp.models import Location
from apps.notificationsapp.services.notification_service import NotificationService
from apps.rolesapp.models import Role, UserRole
from apps.shopapp.models import Shop, ShopHours
from apps.specialistsapp.models import Specialist


class ShopService:
    @staticmethod
    @transaction.atomic
    def create_shop(company, shop_data, manager_data=None):
        """Create a new shop with manager if provided"""
        # Create location if provided
        location = None
        if "location" in shop_data and shop_data["location"]:
            location_data = shop_data.pop("location")
            location = Location.objects.create(**location_data)

        # Create the shop
        shop = Shop.objects.create(company=company, location=location, **shop_data)

        # Add default operating hours
        for weekday in range(7):
            # Default 9 AM to 6 PM, closed on Friday
            is_closed = weekday == 5  # Friday
            from_hour = "09:00:00"
            to_hour = "18:00:00"

            ShopHours.objects.create(
                shop=shop,
                weekday=weekday,
                from_hour=from_hour,
                to_hour=to_hour,
                is_closed=is_closed,
            )

        # Create manager if data provided
        if manager_data:
            phone_number = manager_data.pop("phone_number")

            # Check if user exists
            user, created = User.objects.get_or_create(
                phone_number=phone_number,
                defaults={
                    "user_type": "employee",
                    "is_verified": True,
                    "profile_completed": True,
                },
            )

            # Create employee record
            employee = Employee.objects.create(
                user=user, shop=shop, position="manager", **manager_data
            )

            # Assign manager role
            manager_role = Role.objects.get(role_type="shop_manager", shop=shop)
            UserRole.objects.create(user=user, role=manager_role)

            # Update shop with manager
            shop.manager = user
            shop.save()

            # Send notification to manager
            NotificationService.send_notification(
                user_id=user.id,
                notification_type="shop_manager_assigned",
                data={"shop_name": shop.name, "company_name": company.name},
            )

        return shop

    @staticmethod
    def get_user_shops(user):
        """Get all shops a user has access to"""
        from apps.rolesapp.services.permission_resolver import PermissionResolver

        return PermissionResolver.get_user_shops(user)

    @staticmethod
    @transaction.atomic
    def update_shop(shop_id, shop_data, user_id):
        """Update shop details"""
        shop = Shop.objects.get(id=shop_id)
        user = User.objects.get(id=user_id)

        # Check if user has permission to update shop
        from apps.rolesapp.services.permission_resolver import PermissionResolver

        if not PermissionResolver.has_shop_permission(user, shop_id, "shop", "edit"):
            raise PermissionError("User does not have permission to update this shop")

        # Update location if provided
        if "location" in shop_data and shop_data["location"]:
            location_data = shop_data.pop("location")

            if shop.location:
                # Update existing location
                for key, value in location_data.items():
                    setattr(shop.location, key, value)
                shop.location.save()
            else:
                # Create new location
                location = Location.objects.create(**location_data)
                shop.location = location

        # Update shop fields
        for key, value in shop_data.items():
            if hasattr(shop, key):
                setattr(shop, key, value)

        shop.save()
        return shop

    @staticmethod
    @transaction.atomic
    def verify_shop(shop_id, verified_by_id):
        """Verify a shop and its specialists"""
        shop = Shop.objects.get(id=shop_id)
        verified_by = User.objects.get(id=verified_by_id)

        # Check if user has permission to verify shops
        from apps.rolesapp.services.permission_resolver import PermissionResolver

        if not PermissionResolver.has_permission(verified_by, "shop", "edit"):
            raise PermissionError("User does not have permission to verify shops")

        shop.is_verified = True
        shop.verification_date = timezone.now()
        shop.save()

        # Also verify all specialists in this shop
        specialists = Specialist.objects.filter(employee__shop=shop)
        specialists.update(is_verified=True)

        # Send notification to shop manager
        if shop.manager:
            NotificationService.send_notification(
                user_id=shop.manager.id,
                notification_type="shop_verified",
                data={"shop_name": shop.name},
            )

        # Send notification to company owner
        company_owner = shop.company.owner
        if company_owner:
            NotificationService.send_notification(
                user_id=company_owner.id,
                notification_type="shop_verified",
                data={"shop_name": shop.name, "company_name": shop.company.name},
            )

        return shop

    @staticmethod
    def get_closest_shops(location, radius=10, city=None, category_id=None):
        """Get shops within a radius (km) of a location"""
        from apps.geoapp.services.geo_service import GeoService

        # Base query for verified and active shops
        shops = Shop.objects.filter(is_verified=True, is_active=True)

        # Filter by city if provided
        if city:
            shops = shops.filter(location__city__iexact=city)

        # Filter by category if provided
        if category_id:
            shops = shops.filter(services__category__id=category_id).distinct()

        # Find nearby shops
        shop_ids = GeoService.find_nearby_entities(location, radius, "shop")
        nearby_shops = shops.filter(id__in=shop_ids)

        return nearby_shops

    @staticmethod
    def get_top_shops(city=None, category_id=None, limit=10):
        """Get top shops based on ratings and booking count"""
        # Base query for verified and active shops
        shops = Shop.objects.filter(is_verified=True, is_active=True)

        # Filter by city if provided
        if city:
            shops = shops.filter(location__city__iexact=city)

        # Filter by category if provided
        if category_id:
            shops = shops.filter(services__category__id=category_id).distinct()

        # Get top shops based on reviews and booking count
        from django.contrib.contenttypes.models import ContentType
        from django.db.models import Avg, Case, Count, F, FloatField, Value, When

        shop_type = ContentType.objects.get_for_model(Shop)

        # Get review statistics
        shops = shops.annotate(
            review_count=Count(
                Case(When(review__content_type=shop_type, then=1), default=None),
                distinct=True,
            ),
            booking_count=Count("appointments", distinct=True),
            avg_rating=Avg(
                Case(
                    When(review__content_type=shop_type, then=F("review__rating")),
                    default=None,
                    output_field=FloatField(),
                )
            ),
        )

        # Calculate weighted score
        shops = shops.annotate(
            weighted_score=Case(
                When(
                    review_count__gt=0,
                    then=F("avg_rating") * 0.6 + (F("booking_count") / Value(10.0)) * 0.4,
                ),
                default=F("booking_count") / Value(10.0),
                output_field=FloatField(),
            )
        )

        # Order by weighted score and limit
        return shops.order_by("-weighted_score")[:limit]

    @staticmethod
    def check_username_availability(username):
        """Check if a username is available for a shop"""
        return not Shop.objects.filter(username=username).exists()

    @staticmethod
    def generate_username_suggestion(shop_name):
        """Generate a username suggestion based on shop name"""
        import random
        import re

        # Convert to lowercase and replace spaces with underscores
        base_username = re.sub(r"[^\w\s]", "", shop_name.lower()).replace(" ", "_")

        # Limit length
        if len(base_username) > 40:
            base_username = base_username[:40]

        # Check if available
        if not Shop.objects.filter(username=base_username).exists():
            return base_username

        # Try with random suffix
        for _ in range(5):
            suffix = str(random.randint(1, 999))
            username = f"{base_username}_{suffix}"

            if not Shop.objects.filter(username=username).exists():
                return username

        # Last resort: append timestamp
        import time

        username = f"{base_username}_{int(time.time())}"
        return username
