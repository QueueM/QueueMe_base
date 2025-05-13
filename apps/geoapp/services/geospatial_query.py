import logging

from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.db.models import ExpressionWrapper, F, FloatField

logger = logging.getLogger(__name__)


class GeospatialQueryService:
    """Service for efficient spatial searches and queries"""

    @staticmethod
    def find_nearby_entities(
        latitude, longitude, entity_type, radius=5.0, max_results=20, filters=None
    ):
        """
        Find entities near a location using R-Tree spatial indexing for efficiency

        Args:
            latitude, longitude: Search point coordinates
            entity_type: Type of entity ('shop', 'specialist', etc.)
            radius: Search radius in kilometers
            max_results: Maximum number of results to return
            filters: Additional filters to apply

        Returns:
            List of nearby entities with distance information
        """
        try:
            # Create a point
            point = Point(float(longitude), float(latitude), srid=4326)

            # Import entity models based on type
            if entity_type == "shop":
                from apps.shopapp.models import Shop
                from apps.shopapp.serializers import ShopSerializer

                model_class = Shop
                serializer_class = ShopSerializer
                location_field = "location__coordinates"
            elif entity_type == "specialist":
                from apps.specialistsapp.models import Specialist
                from apps.specialistsapp.serializers import SpecialistSerializer

                model_class = Specialist
                serializer_class = SpecialistSerializer
                location_field = "employee__shop__location__coordinates"
            elif entity_type == "service":
                from apps.serviceapp.models import Service
                from apps.serviceapp.serializers import ServiceSerializer

                model_class = Service
                serializer_class = ServiceSerializer
                location_field = "shop__location__coordinates"
            else:
                raise ValueError(f"Unsupported entity type: {entity_type}")

            # Start with base query with spatial filter
            queryset = model_class.objects.filter(
                **{f"{location_field}__distance_lte": (point, D(km=radius))}
            )

            # Apply city filter if enabled
            same_city_only = filters.get("same_city_only") == "true" if filters else False
            if same_city_only:
                # Find the city for the reference point
                from ..models import City

                ref_city = (
                    City.objects.annotate(distance=Distance("location", point))
                    .order_by("distance")
                    .first()
                )

                if ref_city:
                    # Filter to only include entities in the same city
                    if entity_type == "shop":
                        queryset = queryset.filter(location__city=ref_city)
                    elif entity_type == "specialist":
                        queryset = queryset.filter(employee__shop__location__city=ref_city)
                    elif entity_type == "service":
                        queryset = queryset.filter(shop__location__city=ref_city)

            # Apply additional filters from request
            if filters:
                for key, value in filters.items():
                    if key not in ["same_city_only", "include_travel_time"] and value:
                        queryset = queryset.filter(**{key: value})

            # Annotate with distance
            queryset = queryset.annotate(distance=Distance(location_field, point))

            # Convert distance to kilometers
            queryset = queryset.annotate(
                distance_km=ExpressionWrapper(
                    F("distance") * 100, output_field=FloatField()  # Convert to km
                )
            )

            # Order by distance and limit results
            queryset = queryset.order_by("distance")[:max_results]

            # Include travel time if requested
            include_travel_time = filters.get("include_travel_time") == "true" if filters else False

            # Prepare results
            results = []
            for entity in queryset:
                # Serialize the entity
                serializer = serializer_class(entity)
                entity_data = serializer.data

                # Add distance information
                entity_data["distance_km"] = round(entity.distance_km, 2)

                # Add travel time if requested
                if include_travel_time:
                    from .travel_time_service import TravelTimeService

                    # Get entity's location
                    if entity_type == "shop":
                        entity_point = entity.location.coordinates
                    elif entity_type == "specialist":
                        entity_point = entity.employee.shop.location.coordinates
                    elif entity_type == "service":
                        entity_point = entity.shop.location.coordinates

                    # Calculate travel time
                    entity_data["travel_time_minutes"] = TravelTimeService.estimate_travel_time(
                        point, entity_point
                    )

                results.append(entity_data)

            return results
        except Exception as e:
            logger.error(f"Error in find_nearby_entities: {str(e)}")
            raise

    @staticmethod
    def optimize_service_area(shop_id, service_type=None):
        """
        Determine the optimal service radius for a shop based on historical bookings

        Args:
            shop_id: ID of the shop
            service_type: Optional service type filter

        Returns:
            Dictionary with optimal radius and related data
        """
        try:
            from apps.bookingapp.models import Appointment
            from apps.shopapp.models import Shop

            # Get the shop
            shop = Shop.objects.get(id=shop_id)
            shop_location = shop.location.coordinates

            # Get historical in-home bookings
            booking_query = Appointment.objects.filter(
                shop_id=shop_id, service__service_location__in=["in_home", "both"]
            )

            if service_type:
                booking_query = booking_query.filter(service__service_type=service_type)

            # Get customer locations
            customer_locations = []
            for booking in booking_query:
                # Skip if customer has no location
                if not hasattr(booking.customer, "location") or not booking.customer.location:
                    continue

                customer_location = booking.customer.location.coordinates

                # Calculate distance
                distance_km = shop_location.distance(customer_location) * 100  # Convert to km

                customer_locations.append(
                    {
                        "distance_km": distance_km,
                        "booking_id": str(booking.id),
                        "revenue": float(booking.service.price),
                    }
                )

            # Sort by distance
            customer_locations.sort(key=lambda x: x["distance_km"])

            # Calculate profitability by distance
            distance_thresholds = [1, 2, 3, 5, 7, 10, 15, 20, 25, 30]
            profitability_data = []

            for threshold in distance_thresholds:
                # Count bookings within threshold
                bookings_within = [
                    loc for loc in customer_locations if loc["distance_km"] <= threshold
                ]
                count = len(bookings_within)

                # Skip if no bookings
                if count == 0:
                    continue

                # Calculate revenue
                revenue = sum(loc["revenue"] for loc in bookings_within)

                # Estimate cost (simplified)
                # Assume cost increases with distance
                avg_distance = sum(loc["distance_km"] for loc in bookings_within) / count
                estimated_cost = avg_distance * 5  # Simplified cost model

                profit = revenue - estimated_cost

                profitability_data.append(
                    {
                        "distance_threshold": threshold,
                        "booking_count": count,
                        "revenue": revenue,
                        "estimated_cost": estimated_cost,
                        "profit": profit,
                    }
                )

            # Find optimal radius (maximum profit)
            if profitability_data:
                optimal_threshold = max(profitability_data, key=lambda x: x["profit"])

                return {
                    "optimal_radius_km": optimal_threshold["distance_threshold"],
                    "expected_booking_count": optimal_threshold["booking_count"],
                    "expected_profit": optimal_threshold["profit"],
                    "profitability_data": profitability_data,
                }
            else:
                # No data available
                return {
                    "optimal_radius_km": 5,  # Default
                    "message": "Insufficient booking data for optimization",
                    "profitability_data": [],
                }
        except Exception as e:
            logger.error(f"Error optimizing service area: {str(e)}")
            raise
