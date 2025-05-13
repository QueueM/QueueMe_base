import random
import re
from datetime import timedelta

from django.db.models import Avg, Count
from django.utils import timezone

from apps.shopapp.models import Shop


def generate_shop_username(name):
    """Generate a unique username for a shop based on name"""
    # Convert to lowercase and replace spaces with underscores
    base_username = re.sub(r"[^\w\s]", "", name.lower()).replace(" ", "_")

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


def get_trending_shops(city=None, days=7, limit=10):
    """Get trending shops based on recent bookings and follows"""
    from apps.bookingapp.models import Appointment
    from apps.shopapp.models import ShopFollower

    # Start with verified and active shops
    queryset = Shop.objects.filter(is_verified=True, is_active=True)

    # Filter by city if provided
    if city:
        queryset = queryset.filter(location__city__iexact=city)

    # Calculate date range
    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)

    # Count recent bookings
    recent_bookings = (
        Appointment.objects.filter(start_time__gte=start_date, start_time__lte=end_date)
        .values("shop")
        .annotate(booking_count=Count("id"))
    )

    booking_counts = {item["shop"]: item["booking_count"] for item in recent_bookings}

    # Count recent follows
    recent_follows = (
        ShopFollower.objects.filter(created_at__gte=start_date, created_at__lte=end_date)
        .values("shop")
        .annotate(follow_count=Count("id"))
    )

    follow_counts = {item["shop"]: item["follow_count"] for item in recent_follows}

    # Calculate trending score for each shop
    trending_shops = []
    for shop in queryset:
        booking_score = booking_counts.get(shop.id, 0) * 2  # Weight bookings more
        follow_score = follow_counts.get(shop.id, 0)
        trending_score = booking_score + follow_score

        if trending_score > 0:
            trending_shops.append({"shop": shop, "score": trending_score})

    # Sort by trending score and limit
    trending_shops.sort(key=lambda x: x["score"], reverse=True)
    return [item["shop"] for item in trending_shops[:limit]]


def format_shop_hours_for_display(shop):
    """Format shop hours for display"""
    from django.utils.translation import get_language

    current_language = get_language()

    weekday_names = {
        0: "Sunday" if current_language == "en" else "الأحد",
        1: "Monday" if current_language == "en" else "الاثنين",
        2: "Tuesday" if current_language == "en" else "الثلاثاء",
        3: "Wednesday" if current_language == "en" else "الأربعاء",
        4: "Thursday" if current_language == "en" else "الخميس",
        5: "Friday" if current_language == "en" else "الجمعة",
        6: "Saturday" if current_language == "en" else "السبت",
    }

    closed_text = "Closed" if current_language == "en" else "مغلق"

    hours = shop.hours.order_by("weekday")

    formatted_hours = []
    for hour in hours:
        if hour.is_closed:
            formatted_hours.append(
                {
                    "day": weekday_names[hour.weekday],
                    "hours": closed_text,
                    "is_closed": True,
                }
            )
        else:
            from_time = hour.from_hour.strftime("%I:%M %p")
            to_time = hour.to_hour.strftime("%I:%M %p")

            formatted_hours.append(
                {
                    "day": weekday_names[hour.weekday],
                    "hours": f"{from_time} - {to_time}",
                    "is_closed": False,
                    "from_hour": from_time,
                    "to_hour": to_time,
                }
            )

    return formatted_hours


def get_shop_stats(shop):
    """Get key statistics for a shop"""
    from django.contrib.contenttypes.models import ContentType

    from apps.bookingapp.models import Appointment
    from apps.reviewapp.models import Review

    # Get content type for shop
    shop_type = ContentType.objects.get_for_model(Shop)

    # Count reviews
    review_count = Review.objects.filter(content_type=shop_type, object_id=shop.id).count()

    # Calculate average rating
    avg_rating = (
        Review.objects.filter(content_type=shop_type, object_id=shop.id).aggregate(Avg("rating"))[
            "rating__avg"
        ]
        or 0
    )

    # Count total bookings
    booking_count = Appointment.objects.filter(shop=shop).count()

    # Count followers
    follower_count = shop.followers.count()

    # Count services and specialists
    service_count = shop.services.count()
    specialist_count = shop.get_specialist_count()

    return {
        "review_count": review_count,
        "avg_rating": round(avg_rating, 1),
        "booking_count": booking_count,
        "follower_count": follower_count,
        "service_count": service_count,
        "specialist_count": specialist_count,
    }
