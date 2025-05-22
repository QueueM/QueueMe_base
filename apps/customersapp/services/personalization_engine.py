import random

from django.db.models import Avg, Case, Count, F, FloatField, Sum, Value, When
from django.db.models.functions import Coalesce


class PersonalizationEngine:
    """
    Advanced personalization engine for content recommendation
    """

    @classmethod
    def get_recommendations(cls, customer, content_type="all", limit=10):
        """
        Get personalized content recommendations for a customer

        content_type: 'all', 'shops', 'specialists', 'services', 'reels'
        """
        if content_type == "all":
            # Combine recommendations from different types
            shops = cls._recommend_shops(customer, limit=3)
            specialists = cls._recommend_specialists(customer, limit=3)
            services = cls._recommend_services(customer, limit=3)
            reels = cls._recommend_reels(customer, limit=3)

            # Combine and return
            return {
                "shops": shops,
                "specialists": specialists,
                "services": services,
                "reels": reels,
            }
        elif content_type == "shops":
            return {"shops": cls._recommend_shops(customer, limit=limit)}
        elif content_type == "specialists":
            return {"specialists": cls._recommend_specialists(customer, limit=limit)}
        elif content_type == "services":
            return {"services": cls._recommend_services(customer, limit=limit)}
        elif content_type == "reels":
            return {"reels": cls._recommend_reels(customer, limit=limit)}
        else:
            raise ValueError(f"Invalid content type: {content_type}")

    @classmethod
    def _recommend_shops(cls, customer, limit=10):
        """
        Recommend shops based on customer preferences
        """
        from apps.shopapp.models import Shop
        from apps.shopapp.serializers import ShopMiniSerializer

        # Get customer's favorite shop IDs to exclude
        favorite_shop_ids = customer.favorite_shops.values_list("shop_id", flat=True)

        # Get customer's city for localized recommendations
        customer_city = customer.city

        # Get customer's category preferences
        category_ids = customer.category_interests.values_list("category_id", flat=True)

        # Start with shops in same city
        queryset = Shop.objects.filter(is_active=True, is_verified=True)

        # Apply city filter if available
        if customer_city:
            queryset = queryset.filter(city=customer_city)

        # Exclude shops already favorited
        if favorite_shop_ids:
            queryset = queryset.exclude(id__in=favorite_shop_ids)

        # Calculate a relevance score based on multiple factors
        queryset = queryset.annotate(
            # Category match score
            category_match=Coalesce(
                Sum(
                    Case(
                        When(services__category__in=category_ids, then=1.0),
                        default=0.0,
                        output_field=FloatField(),
                    )
                ),
                Value(0.0),
                output_field=FloatField(),
            ),
            # Rating score (0-5)
            rating_score=Coalesce(
                Avg("reviews__rating"), Value(0.0), output_field=FloatField()
            ),
            # Popularity score based on booking count
            popularity=Count("appointments"),
            # Calculate overall relevance score
            relevance_score=(
                F("category_match") * 0.4  # 40% weight to category match
                + F("rating_score") * 0.3  # 30% weight to ratings
                + F("popularity")
                * 0.0001
                * 0.3  # 30% weight to popularity (normalized)
            ),
        ).order_by("-relevance_score", "-is_verified")

        # Limit results
        shops = queryset[:limit]

        # Serialize results
        serializer = ShopMiniSerializer(shops, many=True)
        return serializer.data

    @classmethod
    def _recommend_specialists(cls, customer, limit=10):
        """
        Recommend specialists based on customer preferences
        """
        from apps.specialistsapp.models import Specialist
        from apps.specialistsapp.serializers import SpecialistMiniSerializer

        # Get customer's favorite specialist IDs to exclude
        favorite_specialist_ids = customer.favorite_specialists.values_list(
            "specialist_id", flat=True
        )

        # Get customer's city for localized recommendations
        customer_city = customer.city

        # Get customer's category preferences
        category_interests = list(
            customer.category_interests.order_by("-affinity_score")[:3]
        )
        category_ids = [interest.category_id for interest in category_interests]

        # Start with verified specialists
        queryset = Specialist.objects.filter(is_verified=True, employee__is_active=True)

        # Apply city filter if available
        if customer_city:
            queryset = queryset.filter(employee__shop__city=customer_city)

        # Exclude specialists already favorited
        if favorite_specialist_ids:
            queryset = queryset.exclude(id__in=favorite_specialist_ids)

        # Calculate a relevance score based on multiple factors
        queryset = queryset.annotate(
            # Category match score
            category_match=Coalesce(
                Sum(
                    Case(
                        When(services__category__in=category_ids, then=1.0),
                        default=0.0,
                        output_field=FloatField(),
                    )
                ),
                Value(0.0),
                output_field=FloatField(),
            ),
            # Rating score (0-5)
            rating_score=Coalesce(
                Avg("reviews__rating"), Value(0.0), output_field=FloatField()
            ),
            # Experience score based on years
            experience_score=F("experience_years")
            * 0.1,  # 0.1 per year, up to 1.0 for 10+ years
            # Calculate overall relevance score
            relevance_score=(
                F("category_match") * 0.4  # 40% weight to category match
                + F("rating_score") * 0.4  # 40% weight to ratings
                + F("experience_score") * 0.2  # 20% weight to experience
            ),
        ).order_by("-relevance_score")

        # Limit results
        specialists = queryset[:limit]

        # Serialize results
        serializer = SpecialistMiniSerializer(specialists, many=True)
        return serializer.data

    @classmethod
    def _recommend_services(cls, customer, limit=10):
        """
        Recommend services based on customer preferences
        """
        from apps.serviceapp.models import Service
        from apps.serviceapp.serializers import ServiceMiniSerializer

        # Get customer's favorite service IDs to exclude
        favorite_service_ids = customer.favorite_services.values_list(
            "service_id", flat=True
        )

        # Get customer's city for localized recommendations
        customer_city = customer.city

        # Get customer's category interests with weights
        category_weights = {}
        for interest in customer.category_interests.all():
            category_weights[str(interest.category_id)] = interest.affinity_score

        # Start with active services
        queryset = Service.objects.filter(
            is_active=True, shop__is_active=True, shop__is_verified=True
        )

        # Apply city filter if available
        if customer_city:
            queryset = queryset.filter(shop__city=customer_city)

        # Exclude services already favorited
        if favorite_service_ids:
            queryset = queryset.exclude(id__in=favorite_service_ids)

        # Get top services based on category match and ratings
        queryset = queryset.annotate(
            # Rating score (0-5)
            rating_score=Coalesce(
                Avg("reviews__rating"), Value(0.0), output_field=FloatField()
            ),
            # Booking popularity
            booking_count=Count("appointments"),
        )

        # Apply category weights - this is a sophisticated approach that requires custom sorting
        services = list(
            queryset[: limit * 3]
        )  # Get more than needed for post-processing

        # Calculate custom relevance score including category weights
        for service in services:
            category_id = str(service.category_id)
            category_score = category_weights.get(category_id, 0)

            # Calculate final score
            service.relevance_score = (
                (category_score * 0.6)  # 60% weight to category match
                + (service.rating_score * 0.3)  # 30% weight to ratings
                + (
                    min(service.booking_count * 0.01, 1.0) * 0.1
                )  # 10% weight to popularity (capped)
            )

        # Sort by relevance score (descending)
        services.sort(key=lambda s: s.relevance_score, reverse=True)

        # Take top services
        top_services = services[:limit]

        # Introduce randomness for discovery (shuffle some of the top services)
        # This ensures customers don't always see the same recommendations
        if len(top_services) > 3:
            shuffle_candidates = top_services[2:]  # Keep the top 2 stable
            random.shuffle(shuffle_candidates)
            top_services = top_services[:2] + shuffle_candidates

        # Serialize results
        serializer = ServiceMiniSerializer(top_services, many=True)
        return serializer.data

    @classmethod
    def _recommend_reels(cls, customer, limit=10):
        """
        Recommend reels based on customer preferences
        """
        from apps.reelsapp.models import Reel
        from apps.reelsapp.serializers import ReelMiniSerializer

        # Get customer's city for localized recommendations
        customer_city = customer.city

        # Get customer's category interests
        category_ids = customer.category_interests.values_list("category_id", flat=True)

        # Start with active reels
        queryset = Reel.objects.filter(is_active=True, shop__is_active=True).order_by(
            "-created_at"
        )  # Recency is important for reels

        # Apply city filter if available
        if customer_city:
            queryset = queryset.filter(shop__city=customer_city)

        # Add engagement metrics
        queryset = queryset.annotate(
            like_count=Count("likes"),
            comment_count=Count("comments"),
            share_count=Count("shares"),
            engagement_score=(
                F("like_count") * 1 + F("comment_count") * 2 + F("share_count") * 3
            ),
        )

        # If we have category preferences, boost relevant reels
        if category_ids:
            queryset = queryset.annotate(
                category_match=Case(
                    When(service__category__in=category_ids, then=Value(1.0)),
                    default=Value(0.0),
                    output_field=FloatField(),
                )
            ).order_by("-category_match", "-engagement_score", "-created_at")
        else:
            # Order by engagement and recency
            queryset = queryset.order_by("-engagement_score", "-created_at")

        # Limit results
        reels = queryset[:limit]

        # Serialize results
        serializer = ReelMiniSerializer(reels, many=True)
        return serializer.data
