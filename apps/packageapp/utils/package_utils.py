from django.db.models import Avg, Count, Q
from django.utils.translation import gettext_lazy as _


def calculate_package_metrics(package):
    """
    Calculate advanced metrics for a package.

    Args:
        package: The package to calculate metrics for

    Returns:
        dict: A dictionary containing calculated metrics
    """
    from apps.bookingapp.models import Appointment

    # Assuming Appointment has a package field to track package bookings
    bookings = Appointment.objects.filter(package_id=package.id)

    total_bookings = bookings.count()
    completed_bookings = bookings.filter(status="completed").count()
    cancelled_bookings = bookings.filter(status="cancelled").count()

    # Calculate completion rate
    completion_rate = (
        (completed_bookings / total_bookings * 100) if total_bookings > 0 else 0
    )

    # Calculate average rating if available
    from apps.reviewapp.models import Review

    avg_rating = (
        Review.objects.filter(
            content_type__model="package", object_id=str(package.id)
        ).aggregate(avg_rating=Avg("rating"))["avg_rating"]
        or 0
    )

    # Calculate revenue generated
    revenue = completed_bookings * package.discounted_price

    # Calculate savings provided to customers
    savings = completed_bookings * (package.original_price - package.discounted_price)

    return {
        "total_bookings": total_bookings,
        "completed_bookings": completed_bookings,
        "cancelled_bookings": cancelled_bookings,
        "completion_rate": completion_rate,
        "avg_rating": avg_rating,
        "revenue": revenue,
        "savings": savings,
    }


def calculate_package_roi(package):
    """
    Calculate Return on Investment (ROI) for a package.

    Args:
        package: The package to calculate ROI for

    Returns:
        float: The ROI percentage
    """
    # Get metrics
    metrics = calculate_package_metrics(package)

    # Calculate cost of offering the package (simplified)
    # In a real system, would account for operational costs, discounts, etc.
    cost = package.original_price * 0.7  # Estimated cost (70% of original price)

    # Calculate profit
    profit = metrics["revenue"] - (cost * metrics["completed_bookings"])

    # Calculate ROI
    investment = cost * metrics["completed_bookings"]
    roi = (profit / investment * 100) if investment > 0 else 0

    return roi


def get_similar_packages(package, limit=5):
    """
    Find similar packages based on services, category, and location.

    Args:
        package: The reference package
        limit: Maximum number of packages to return

    Returns:
        queryset: A queryset of similar packages
    """
    from apps.packageapp.models import Package

    # Get services in this package
    service_ids = [ps.service_id for ps in package.services.all()]

    # Find packages with similar services, same category, or location
    similar_packages = (
        Package.objects.filter(
            Q(services__service_id__in=service_ids)
            | Q(primary_category=package.primary_category)
            | Q(package_location=package.package_location)
        )
        .exclude(id=package.id)  # Exclude the reference package
        .filter(shop=package.shop, status="active")  # Same shop  # Only active packages
        .annotate(
            similarity_score=Count(
                "services__service_id", filter=Q(services__service_id__in=service_ids)
            )
        )
        .order_by("-similarity_score")
    )

    return similar_packages[:limit]


def check_package_availability(package_id, date_str):
    """
    Check if a package is available on the specified date.

    Args:
        package_id: The package ID to check
        date_str: Date string in YYYY-MM-DD format

    Returns:
        bool: True if package is available, False otherwise
    """
    from datetime import datetime

    from apps.packageapp.models import Package, PackageAvailability

    try:
        package = Package.objects.get(id=package_id)

        # Check if package is active and available for purchase
        if not package.is_available:
            return False

        # Parse date
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()

        # Check start/end dates
        # unused_unused_today = timezone.now().date()
        if package.start_date and date_obj < package.start_date:
            return False
        if package.end_date and date_obj > package.end_date:
            return False

        # Get day of week (0 = Sunday, 6 = Saturday)
        weekday = date_obj.weekday()
        if weekday == 6:  # Python's Sunday (6) to our Sunday (0)
            weekday = 0
        else:
            weekday += 1

        # Check custom availability
        try:
            availability = PackageAvailability.objects.get(
                package=package, weekday=weekday
            )
            if availability.is_closed:
                return False
        except PackageAvailability.DoesNotExist:
            # If no custom availability, fall back to shop hours
            from apps.shopapp.models import ShopHours

            try:
                shop_hours = ShopHours.objects.get(shop=package.shop, weekday=weekday)
                if shop_hours.is_closed:
                    return False
            except ShopHours.DoesNotExist:
                # No hours defined for this day
                return False

        return True

    except (Package.DoesNotExist, ValueError):
        return False


def format_package_duration(minutes):
    """
    Format package duration in minutes to a human-readable string.

    Args:
        minutes: Duration in minutes

    Returns:
        str: Formatted duration string (e.g., "2 hours 30 minutes")
    """
    if minutes is None or minutes == 0:
        return _("Not specified")

    hours = minutes // 60
    mins = minutes % 60

    if hours > 0 and mins > 0:
        return _("{hours} hours {minutes} minutes").format(hours=hours, minutes=mins)
    elif hours > 0:
        return _("{hours} hours").format(hours=hours)
    else:
        return _("{minutes} minutes").format(minutes=mins)
