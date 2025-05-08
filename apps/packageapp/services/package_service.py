from django.db import transaction
from django.db.models import Avg, Count, F, Q, Sum
from django.utils import timezone

from apps.bookingapp.models import Appointment
from apps.reviewapp.models import Review
from apps.serviceapp.models import Service

from ..models import Package, PackageService
from ..utils.package_utils import calculate_package_metrics, get_similar_packages


class PackageService:
    """
    Service class for package management operations.
    Implements advanced package management functionality and business logic.
    """

    @staticmethod
    def create_package(package_data, services_data):
        """
        Create a new package with services.

        Args:
            package_data: Dictionary with package details
            services_data: List of dictionaries with service details

        Returns:
            Package: The created package instance
        """
        with transaction.atomic():
            # Calculate original price
            service_ids = [s["service_id"] for s in services_data]
            services = Service.objects.filter(id__in=service_ids)
            original_price = sum(service.price for service in services)

            # Create package
            package = Package.objects.create(
                **package_data, original_price=original_price
            )

            # Add services
            for service_data in services_data:
                service_id = service_data.pop("service_id")
                PackageService.objects.create(
                    package=package, service_id=service_id, **service_data
                )

            return package

    @staticmethod
    def update_package(package_id, package_data, services_data=None):
        """
        Update an existing package.

        Args:
            package_id: ID of the package to update
            package_data: Dictionary with updated package details
            services_data: Optional list of dictionaries with updated service details

        Returns:
            Package: The updated package instance
        """
        with transaction.atomic():
            package = Package.objects.get(id=package_id)

            # Update package fields
            for key, value in package_data.items():
                setattr(package, key, value)

            # Update services if provided
            if services_data is not None:
                # Delete existing services
                package.services.all().delete()

                # Add new services
                service_ids = [s["service_id"] for s in services_data]
                services = Service.objects.filter(id__in=service_ids)
                original_price = sum(service.price for service in services)

                package.original_price = original_price

                for service_data in services_data:
                    service_id = service_data.pop("service_id")
                    PackageService.objects.create(
                        package=package, service_id=service_id, **service_data
                    )

            package.save()
            return package

    @staticmethod
    def get_package_details(package_id):
        """
        Get detailed information about a package, including metrics.

        Args:
            package_id: ID of the package

        Returns:
            dict: Package details with metrics
        """
        package = Package.objects.get(id=package_id)

        # Get services
        services = package.services.all().select_related("service")

        # Get metrics
        metrics = calculate_package_metrics(package)

        # Get similar packages
        similar = get_similar_packages(package)

        # Get reviews
        reviews = (
            Review.objects.filter(
                content_type__model="package", object_id=str(package_id)
            )
            .select_related("user")
            .order_by("-created_at")
        )

        return {
            "package": package,
            "services": services,
            "metrics": metrics,
            "similar_packages": similar,
            "reviews": reviews,
        }

    @staticmethod
    def get_recommended_packages(user_id):
        """
        Get personalized package recommendations for a user.

        Args:
            user_id: ID of the user to get recommendations for

        Returns:
            list: Recommended packages for the user
        """
        from apps.authapp.models import User
        from apps.customersapp.models import Customer

        try:
            user = User.objects.get(id=user_id)

            # For non-customers, return top-rated packages
            if user.user_type != "customer":
                return PackageService.get_popular_packages()

            # Get customer information
            try:
                customer = Customer.objects.get(user=user)
                city = customer.city
            except Customer.DoesNotExist:
                # If customer profile doesn't exist, just filter by active status
                return PackageService.get_popular_packages()

            # Get user's booking history
            appointments = Appointment.objects.filter(customer=user)

            # Get booked services
            service_ids = appointments.values_list("service_id", flat=True).distinct()

            # Get categories of booked services
            from apps.serviceapp.models import Service

            category_ids = (
                Service.objects.filter(id__in=service_ids)
                .values_list("category_id", flat=True)
                .distinct()
            )

            # Get packages in the same city, with similar categories or services
            recommended = (
                Package.objects.filter(status="active", shop__location__city=city)
                .filter(
                    Q(primary_category_id__in=category_ids)
                    | Q(services__service_id__in=service_ids)
                )
                .exclude(
                    id__in=appointments.filter(package_id__isnull=False).values_list(
                        "package_id", flat=True
                    )
                )
                .annotate(
                    relevance_score=Count(
                        "services__service_id",
                        filter=Q(services__service_id__in=service_ids),
                    )
                    + (F("discount_percentage") * 0.1)  # Boost higher discounts
                )
                .order_by("-relevance_score", "-created_at")
                .distinct()
            )

            # If not enough recommendations, add top-rated packages
            if recommended.count() < 10:
                popular = PackageService.get_popular_packages(
                    limit=10 - recommended.count(), city=city
                )
                # Combine querysets without duplicates
                package_ids = list(recommended.values_list("id", flat=True))
                additional = [p for p in popular if p.id not in package_ids]

                # Convert recommended queryset to list for combining
                recommended_list = list(recommended)
                recommended_list.extend(additional)
                return recommended_list

            return recommended

        except User.DoesNotExist:
            return []

    @staticmethod
    def get_popular_packages(shop_id=None, category_id=None, city=None, limit=10):
        """
        Get most popular packages based on booking frequency and ratings.

        Args:
            shop_id: Optional shop ID to filter by
            category_id: Optional category ID to filter by
            city: Optional city to filter by
            limit: Maximum number of packages to return

        Returns:
            list: Popular packages
        """
        # Base query for active packages
        queryset = Package.objects.filter(status="active")

        # Apply filters
        if shop_id:
            queryset = queryset.filter(shop_id=shop_id)

        if category_id:
            queryset = queryset.filter(primary_category_id=category_id)

        if city:
            queryset = queryset.filter(shop__location__city=city)

        # Annotate with booking count and average rating
        from django.contrib.contenttypes.models import ContentType

        package_type = ContentType.objects.get(app_label="packageapp", model="package")

        popular = queryset.annotate(
            booking_count=Count(
                "id",
                filter=Q(
                    # Reference to appointment.package_id
                    Q(
                        id__in=Appointment.objects.filter(
                            package_id__isnull=False
                        ).values_list("package_id", flat=True)
                    )
                ),
            ),
            avg_rating=Avg(
                "id",
                filter=Q(
                    # Reference to generic foreign key in Review
                    Q(
                        id__in=Review.objects.filter(
                            content_type=package_type
                        ).values_list("object_id", flat=True)
                    )
                ),
            ),
            discount_value=F("original_price") - F("discounted_price"),
        ).order_by("-booking_count", "-avg_rating", "-discount_value")[:limit]

        return popular

    @staticmethod
    @transaction.atomic
    def toggle_package_status(package_id, new_status):
        """
        Toggle a package's status.

        Args:
            package_id: ID of the package
            new_status: New status for the package

        Returns:
            Package: Updated package instance
        """
        package = Package.objects.get(id=package_id)

        # Validate status transition
        valid_statuses = ["active", "inactive", "upcoming", "expired"]
        if new_status not in valid_statuses:
            raise ValueError(f"Invalid status: {new_status}")

        package.status = new_status
        package.save(update_fields=["status"])

        return package

    @staticmethod
    def get_shop_package_stats(shop_id):
        """
        Get comprehensive package statistics for a shop.

        Args:
            shop_id: ID of the shop

        Returns:
            dict: Statistics about the shop's packages
        """
        # Get all packages for the shop
        packages = Package.objects.filter(shop_id=shop_id)

        # Count by status
        status_counts = packages.values("status").annotate(count=Count("id"))

        # Calculate average metrics
        avg_discount = packages.aggregate(avg=Avg("discount_percentage"))["avg"] or 0
        avg_duration = packages.aggregate(avg=Avg("total_duration"))["avg"] or 0

        # Calculate revenue from package bookings
        revenue = (
            Appointment.objects.filter(
                package_id__in=packages.values_list("id", flat=True), status="completed"
            ).aggregate(sum=Sum("package__discounted_price"))["sum"]
            or 0
        )

        # Package with highest booking rate
        from django.contrib.contenttypes.models import ContentType

        package_type = ContentType.objects.get(app_label="packageapp", model="package")

        best_performer = (
            packages.annotate(
                booking_count=Count(
                    "id",
                    filter=Q(
                        # Reference to appointment.package_id
                        Q(
                            id__in=Appointment.objects.filter(
                                package_id__isnull=False
                            ).values_list("package_id", flat=True)
                        )
                    ),
                ),
                avg_rating=Avg(
                    "id",
                    filter=Q(
                        # Reference to generic foreign key in Review
                        Q(
                            id__in=Review.objects.filter(
                                content_type=package_type
                            ).values_list("object_id", flat=True)
                        )
                    ),
                ),
            )
            .order_by("-booking_count", "-avg_rating")
            .first()
        )

        return {
            "total_packages": packages.count(),
            "status_counts": {item["status"]: item["count"] for item in status_counts},
            "avg_discount": avg_discount,
            "avg_duration": avg_duration,
            "total_revenue": revenue,
            "best_performer": best_performer,
        }

    @staticmethod
    def get_package_booking_timeline(package_id, days=30):
        """
        Get booking timeline for a package.

        Args:
            package_id: ID of the package
            days: Number of days to analyze

        Returns:
            dict: Booking data by day
        """
        end_date = timezone.now().date()
        start_date = end_date - timezone.timedelta(days=days - 1)

        # Get bookings for the package in date range
        bookings = Appointment.objects.filter(
            package_id=package_id,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
        )

        # Group by date
        booking_data = {}
        for i in range(days):
            date = start_date + timezone.timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")

            day_bookings = bookings.filter(created_at__date=date)

            booking_data[date_str] = {
                "count": day_bookings.count(),
                "statuses": {
                    status: day_bookings.filter(status=status).count()
                    for status in ["scheduled", "confirmed", "completed", "cancelled"]
                },
            }

        return booking_data
