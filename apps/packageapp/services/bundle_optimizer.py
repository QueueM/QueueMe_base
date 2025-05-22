import itertools

from django.db.models import Avg, Count, Q


class BundleOptimizer:
    """
    Advanced service for optimizing service bundles.
    Contains algorithms for optimal service sequencing and bundle creation.
    """

    @staticmethod
    def optimize_service_sequence(services):
        """
        Determine the optimal sequence of services in a bundle.
        Considers service dependencies, preparation requirements,
        and optimal customer experience flow.

        Args:
            services: List of Service objects to sequence

        Returns:
            list: The same Service objects in an optimal order
        """
        # Convert list to list if it's a queryset
        service_list = list(services)

        if not service_list:
            return []

        # Create a directed graph of service dependencies
        # For example, a hair wash might need to come before a haircut
        dependencies = BundleOptimizer._analyze_service_dependencies(service_list)

        # Create a topological ordering based on dependencies
        ordered_services = BundleOptimizer._topological_sort(service_list, dependencies)

        # If no clear dependencies, optimize based on other factors
        if not dependencies or len(ordered_services) != len(service_list):
            ordered_services = BundleOptimizer._optimize_by_category_and_duration(
                service_list
            )

        return ordered_services

    @staticmethod
    def _analyze_service_dependencies(services):
        """
        Analyze dependencies between services.
        This is a simplified implementation - in a real system, this could use
        machine learning based on historical booking patterns or explicitly defined
        dependencies in the service configurations.

        Args:
            services: List of Service objects

        Returns:
            dict: Graph of service dependencies {service_id: [dependent_service_ids]}
        """
        dependencies = {}

        # Get all service IDs
        # unused_unused_service_ids = [s.id for s in services]

        # Check for common categories that imply ordering
        preparation_categories = ["washing", "prep", "setup"]
        finishing_categories = ["finish", "styling", "polish"]

        for service in services:
            dependencies[service.id] = []

            # Get category name (lowercase for comparison)
            category_name = service.category.name.lower() if service.category else ""

            # If this is a preparation service, it should come before others
            if any(prep in category_name for prep in preparation_categories):
                for other in services:
                    if service.id != other.id and not any(
                        prep in other.category.name.lower()
                        for prep in preparation_categories
                    ):
                        dependencies[other.id].append(service.id)

            # If this is a finishing service, it should come after others
            if any(finish in category_name for finish in finishing_categories):
                for other in services:
                    if service.id != other.id and not any(
                        finish in other.category.name.lower()
                        for finish in finishing_categories
                    ):
                        dependencies[service.id].append(other.id)

        return dependencies

    @staticmethod
    def _topological_sort(services, dependencies):
        """
        Perform a topological sort of services based on dependencies.

        Args:
            services: List of Service objects
            dependencies: Dict mapping service IDs to lists of dependent service IDs

        Returns:
            list: Ordered Service objects
        """
        # Create a mapping of ID to Service object
        service_map = {s.id: s for s in services}

        # Track visited nodes and the current path
        visited = set()
        temp = set()
        order = []

        def visit(service_id):
            """Recursive function to visit nodes in topological order"""
            if service_id in temp:
                # Cycle detected, return False
                return False

            if service_id in visited:
                return True

            temp.add(service_id)

            # Visit all dependencies
            for dep_id in dependencies.get(service_id, []):
                if dep_id in service_map and not visit(dep_id):
                    return False

            temp.remove(service_id)
            visited.add(service_id)
            order.append(service_id)
            return True

        # Visit all services
        for service in services:
            if service.id not in visited:
                if not visit(service.id):
                    # Cycle detected, fall back to simpler ordering
                    return BundleOptimizer._optimize_by_category_and_duration(services)

        # Convert ordered IDs back to Service objects
        return [service_map[service_id] for service_id in order]

    @staticmethod
    def _optimize_by_category_and_duration(services):
        """
        Optimize service sequence based on category grouping and duration.
        This is a fallback when no clear dependencies exist.

        Args:
            services: List of Service objects

        Returns:
            list: Ordered Service objects
        """
        # Group services by category
        category_groups = {}
        for service in services:
            category_id = service.category_id
            if category_id not in category_groups:
                category_groups[category_id] = []
            category_groups[category_id].append(service)

        # Within each category, sort by duration (shortest first)
        for category_id in category_groups:
            category_groups[category_id].sort(key=lambda s: s.duration)

        # Order categories by average duration (shortest first)
        categories = list(category_groups.keys())
        categories.sort(
            key=lambda c: sum(s.duration for s in category_groups[c])
            / len(category_groups[c])
        )

        # Build final ordered list
        ordered_services = []
        for category_id in categories:
            ordered_services.extend(category_groups[category_id])

        return ordered_services

    @staticmethod
    def suggest_optimal_discounts(services, target_discount_percentage=None):
        """
        Suggest optimal discount amounts for a service bundle.
        Can target a specific discount percentage or find the optimal discount
        based on market data and business rules.

        Args:
            services: List of Service objects in the bundle
            target_discount_percentage: Optional target discount percentage

        Returns:
            tuple: (optimal_original_price, optimal_discounted_price, discount_percentage)
        """
        from apps.packageapp.models import Package

        # Calculate bundle original price
        original_price = sum(service.price for service in services)

        if target_discount_percentage:
            # Calculate discounted price based on target percentage
            discount_amount = original_price * (target_discount_percentage / 100)
            discounted_price = original_price - discount_amount
            return (original_price, discounted_price, target_discount_percentage)

        # If no target specified, let's find an optimal discount

        # Check market average for similar bundles
        service_count = len(services)
        category_ids = {s.category_id for s in services}

        # Find similar packages (same number of services or overlapping categories)
        similar_packages = (
            Package.objects.filter(
                Q(services__count=service_count)
                | Q(services__service__category_id__in=category_ids)
            )
            .annotate(service_count=Count("services"))
            .distinct()
        )

        if similar_packages.exists():
            # Calculate average discount percentage of similar packages
            avg_discount = (
                similar_packages.aggregate(avg=Avg("discount_percentage"))["avg"] or 15
            )  # Default to 15% if no data

            # Calculate discounted price
            discount_amount = original_price * (avg_discount / 100)
            discounted_price = original_price - discount_amount

            return (original_price, discounted_price, avg_discount)

        # Fallback to business rules
        base_discount = 10  # Base 10% discount

        # Add extra discount based on service count
        if service_count >= 5:
            base_discount += 10  # Extra 10% for 5+ services
        elif service_count >= 3:
            base_discount += 5  # Extra 5% for 3-4 services

        # Calculate discounted price
        discount_amount = original_price * (base_discount / 100)
        discounted_price = original_price - discount_amount

        return (original_price, discounted_price, base_discount)

    @staticmethod
    def recommend_complementary_services(services, shop_id, max_recommendations=3):
        """
        Recommend additional services that complement the given services.

        Args:
            services: List of Service objects already in the bundle
            shop_id: Shop ID to get recommendations from
            max_recommendations: Maximum number of recommendations

        Returns:
            list: Recommended Service objects
        """
        from apps.bookingapp.models import Appointment
        from apps.serviceapp.models import Service

        # Get IDs of services already in the bundle
        service_ids = [s.id for s in services]

        # Get categories of services in the bundle
        category_ids = {s.category_id for s in services}

        # Find frequently booked together services
        # This could be based on historical booking data

        # Method 1: Find services commonly booked on the same day
        common_services = (
            Service.objects.filter(shop_id=shop_id)
            .exclude(id__in=service_ids)
            .annotate(
                booking_correlation=Count(
                    "appointments",
                    filter=Q(
                        appointments__customer__in=Appointment.objects.filter(
                            service_id__in=service_ids
                        ).values("customer")
                    ),
                )
            )
            .order_by("-booking_correlation")
        )

        # If we have results using method 1, return them
        if common_services.filter(booking_correlation__gt=0).exists():
            return list(
                common_services.filter(booking_correlation__gt=0)[:max_recommendations]
            )

        # Method 2: Find services in related categories
        related_services = Service.objects.filter(
            shop_id=shop_id,
            category__parent_id__in=category_ids,  # Services in child categories
        ).exclude(id__in=service_ids)

        if related_services.exists():
            return list(related_services[:max_recommendations])

        # Method 3: Fallback to popular services
        popular_services = (
            Service.objects.filter(shop_id=shop_id)
            .exclude(id__in=service_ids)
            .annotate(booking_count=Count("appointments"))
            .order_by("-booking_count")
        )

        return list(popular_services[:max_recommendations])

    @staticmethod
    def suggest_package_bundles(
        shop_id, min_services=2, max_services=5, max_suggestions=3
    ):
        """
        Suggest potential service bundles based on booking patterns.

        Args:
            shop_id: Shop ID to suggest bundles for
            min_services: Minimum services in a bundle
            max_services: Maximum services in a bundle
            max_suggestions: Maximum number of bundle suggestions

        Returns:
            list: List of dictionaries containing bundle suggestions
        """
        from django.contrib.contenttypes.models import ContentType

        from apps.bookingapp.models import Appointment
        from apps.reviewapp.models import Review
        from apps.serviceapp.models import Service

        # Get service type for reviews
        service_type = ContentType.objects.get(app_label="serviceapp", model="service")

        # Get all active services for this shop
        services = Service.objects.filter(shop_id=shop_id, is_active=True).annotate(
            booking_count=Count("appointments"),
            avg_rating=Avg(
                "id",
                filter=Q(
                    id__in=Review.objects.filter(content_type=service_type).values_list(
                        "object_id", flat=True
                    )
                ),
            ),
        )

        # Method 1: Find frequently booked together services
        service_combinations = []

        # For each combination size
        for size in range(min_services, max_services + 1):
            # Get customers who have booked multiple services
            customers_with_multiple = (
                Appointment.objects.filter(service__shop_id=shop_id)
                .values("customer")
                .annotate(service_count=Count("service", distinct=True))
                .filter(service_count__gte=size)
                .values_list("customer", flat=True)
            )

            # For each such customer
            for customer_id in customers_with_multiple[
                :100
            ]:  # Limit to avoid too many combinations
                # Get services they booked
                booked_services = (
                    Appointment.objects.filter(
                        customer_id=customer_id, service__shop_id=shop_id
                    )
                    .values_list("service_id", flat=True)
                    .distinct()
                )

                # If they booked at least 'size' different services
                if len(booked_services) >= size:
                    # Consider combinations of exactly 'size' services
                    for combo in itertools.combinations(booked_services, size):
                        service_combinations.append(combo)

        # Count frequency of each combination
        from collections import Counter

        combo_counts = Counter(service_combinations)

        # Get the most common combinations
        suggestions = []
        for combo, count in combo_counts.most_common(max_suggestions):
            combo_services = Service.objects.filter(id__in=combo)

            # Skip if any service is inactive
            if any(not s.is_active for s in combo_services):
                continue

            original_price = sum(s.price for s in combo_services)

            # Suggest discount based on combination frequency
            if count >= 10:
                discount = 20  # 20% for very common combinations
            elif count >= 5:
                discount = 15  # 15% for moderately common
            else:
                discount = 10  # 10% for less common

            discounted_price = original_price * (1 - discount / 100)

            suggestions.append(
                {
                    "services": list(combo_services),
                    "original_price": original_price,
                    "discounted_price": discounted_price,
                    "discount_percentage": discount,
                    "frequency": count,
                }
            )

        # If we don't have enough suggestions, add some based on categories
        if len(suggestions) < max_suggestions:
            # Group services by category
            by_category = {}
            for service in services:
                cat_id = service.category_id
                if cat_id not in by_category:
                    by_category[cat_id] = []
                by_category[cat_id].append(service)

            # Find categories with multiple services
            for cat_id, cat_services in by_category.items():
                if (
                    len(cat_services) >= min_services
                    and len(suggestions) < max_suggestions
                ):
                    # Take top services in this category by booking count
                    top_services = sorted(
                        cat_services, key=lambda s: s.booking_count, reverse=True
                    )
                    bundle_size = min(len(top_services), max_services)
                    bundle_services = top_services[:bundle_size]

                    original_price = sum(s.price for s in bundle_services)
                    discount = 15  # Standard 15% for category bundles
                    discounted_price = original_price * (1 - discount / 100)

                    suggestions.append(
                        {
                            "services": bundle_services,
                            "original_price": original_price,
                            "discounted_price": discounted_price,
                            "discount_percentage": discount,
                            "frequency": 0,  # Not based on frequency
                        }
                    )

        return suggestions
