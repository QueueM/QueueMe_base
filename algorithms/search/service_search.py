import logging
import math
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ServiceSearch:
    """
    Advanced service matching algorithm that finds and ranks services
    based on customer search queries, preferences, and requirements.

    This algorithm enhances service discovery by:
    1. Intelligently parsing search queries for intent
    2. Matching services based on multiple criteria
    3. Considering location, availability, and pricing
    4. Ranking results based on relevance and quality
    5. Supporting complex filters and sorting options
    """

    def __init__(
        self,
        text_match_weight: float = 2.0,
        category_match_weight: float = 1.5,
        rating_weight: float = 1.0,
        price_weight: float = 0.8,
        location_weight: float = 1.2,
        availability_weight: float = 0.7,
        use_stemming: bool = True,
        min_word_length: int = 3,
        fuzzy_matching: bool = True,
    ):
        """
        Initialize the service search algorithm.

        Args:
            text_match_weight: Weight for text matching score
            category_match_weight: Weight for category matching
            rating_weight: Weight for service rating
            price_weight: Weight for price factor (lower price = higher score)
            location_weight: Weight for location proximity
            availability_weight: Weight for service availability
            use_stemming: Whether to use word stemming for better matching
            min_word_length: Minimum word length to consider for matching
            fuzzy_matching: Whether to allow partial/fuzzy matching
        """
        self.text_match_weight = text_match_weight
        self.category_match_weight = category_match_weight
        self.rating_weight = rating_weight
        self.price_weight = price_weight
        self.location_weight = location_weight
        self.availability_weight = availability_weight
        self.use_stemming = use_stemming
        self.min_word_length = min_word_length
        self.fuzzy_matching = fuzzy_matching

        # English stopwords (words to ignore in search)
        self.english_stopwords = {
            "a",
            "an",
            "the",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "with",
            "by",
            "about",
            "of",
            "is",
            "are",
        }

        # Arabic stopwords
        self.arabic_stopwords = {
            "في",
            "من",
            "إلى",
            "على",
            "عن",
            "مع",
            "هذا",
            "هذه",
            "ذلك",
            "تلك",
            "هو",
            "هي",
            "أنا",
            "نحن",
            "أنت",
            "أنتم",
        }

        # For stemming (simplified - in a real implementation would use a proper stemming library)
        self.common_suffixes = ["ing", "ed", "er", "s", "es", "ies"]

    def search_services(
        self,
        query: str,
        services: List[Dict],
        customer_data: Optional[Dict] = None,
        filters: Optional[Dict] = None,
        sort_by: Optional[str] = None,
        location_data: Optional[Dict] = None,
        availability_date: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        include_scores: bool = False,
    ) -> Dict:
        """
        Search and rank services based on query and filters.

        Args:
            query: Search query text
            services: List of service objects with fields:
                - id: Service ID
                - name: Service name
                - description: Service description
                - category_id: Category ID
                - category_name: Category name (optional)
                - price: Price (numeric)
                - duration: Duration in minutes
                - rating: Average rating
                - shop_id: Shop ID
                - shop_name: Shop name
                - shop_location: Location data (lat/lng)
                - tags: Optional tags/keywords
                - is_available: Whether service is generally available
            customer_data: Optional customer preferences and history
            filters: Optional additional filters to apply
            sort_by: Field to sort by (default: relevance score)
            location_data: Optional location for proximity calculation
            availability_date: Optional date string to check availability
            limit: Maximum number of results to return
            offset: Number of results to skip (for pagination)
            include_scores: Whether to include relevance scores in results

        Returns:
            Dictionary containing:
            - results: Matched services
            - total_count: Total number of matching services
            - search_metadata: Information about the search
        """
        # Initialize result
        result = {
            "results": [],
            "total_count": 0,
            "search_metadata": {
                "query": query,
                "filters_applied": filters is not None,
                "location_considered": location_data is not None,
                "availability_checked": availability_date is not None,
            },
        }

        # If no query and no filters, return all services sorted by rating
        if not query and not filters:
            sorted_services = sorted(services, key=lambda s: s.get("rating", 0), reverse=True)

            # Apply pagination
            paginated = sorted_services[offset : offset + limit]

            result["results"] = paginated
            result["total_count"] = len(services)
            return result

        # Prepare query for matching
        processed_query = self._preprocess_query(query)
        query_terms = set(processed_query.split())

        # Calculate search intent and extract key parameters
        search_intent = self._analyze_search_intent(query)

        # Score each service
        scored_services = []

        for service in services:
            # Skip if service doesn't match core filters
            if filters and not self._apply_filters(service, filters):
                continue

            # Get availability if requested
            is_available = True
            if availability_date:
                is_available = self._check_availability(service, availability_date)

            if not is_available and filters and filters.get("available_only", False):
                continue

            # Calculate base text matching score
            text_match_score = self._calculate_text_match(service, query_terms, search_intent)

            # Calculate category match score
            category_match_score = self._calculate_category_match(
                service, search_intent, customer_data
            )

            # Calculate rating score
            rating_score = self._calculate_rating_score(service)

            # Calculate price score
            price_score = self._calculate_price_score(
                service, search_intent.get("price_sensitivity", 0.5)
            )

            # Calculate location score
            location_score = 0.5  # Default score
            if location_data:
                location_score = self._calculate_location_score(service, location_data)

            # Calculate availability score
            availability_score = 1.0 if is_available else 0.3

            # Calculate weighted total score
            total_score = (
                text_match_score * self.text_match_weight
                + category_match_score * self.category_match_weight
                + rating_score * self.rating_weight
                + price_score * self.price_weight
                + location_score * self.location_weight
                + availability_score * self.availability_weight
            )

            # Prepare result object
            result_obj = service.copy()

            # Add score details if requested
            if include_scores:
                result_obj["_score"] = {
                    "total": total_score,
                    "text_match": text_match_score,
                    "category_match": category_match_score,
                    "rating": rating_score,
                    "price": price_score,
                    "location": location_score,
                    "availability": availability_score,
                }
            else:
                result_obj["_score"] = total_score

            scored_services.append(result_obj)

        # Sort services by score or specified field
        if sort_by and sort_by != "relevance":
            sorted_services = sorted(scored_services, key=lambda s: s.get(sort_by, 0), reverse=True)
        else:
            # Sort by relevance score
            sorted_services = sorted(
                scored_services,
                key=lambda s: (
                    s.get("_score", 0)
                    if isinstance(s.get("_score"), (int, float))
                    else s.get("_score", {}).get("total", 0)
                ),
                reverse=True,
            )

        # Apply pagination
        paginated = sorted_services[offset : offset + limit]

        # Remove internal score if not requested
        if not include_scores:
            for service in paginated:
                if "_score" in service:
                    service.pop("_score")

        # Set result fields
        result["results"] = paginated
        result["total_count"] = len(scored_services)

        # Add search metadata
        result["search_metadata"]["intent"] = search_intent

        return result

    def _preprocess_query(self, query: str) -> str:
        """
        Preprocess query text for better matching.
        """
        if not query:
            return ""

        # Lowercase
        query = query.lower()

        # Remove punctuation
        query = re.sub(r"[^\w\s]", " ", query)

        # Split into words
        words = query.split()

        # Filter out stopwords and short words
        filtered_words = []
        for word in words:
            if (
                len(word) >= self.min_word_length
                and word not in self.english_stopwords
                and word not in self.arabic_stopwords
            ):

                # Apply stemming if enabled
                if self.use_stemming:
                    word = self._simple_stem(word)

                filtered_words.append(word)

        # Join back into string
        processed_query = " ".join(filtered_words)

        return processed_query

    def _simple_stem(self, word: str) -> str:
        """
        Simple stemming function to normalize words.
        In a real implementation, would use a proper stemming library.
        """
        # Check for Arabic script (simplified)
        if any("\u0600" <= c <= "\u06ff" for c in word):
            # For Arabic, we'd use a proper Arabic stemmer
            # This is just a placeholder
            return word

        # For English, remove common suffixes
        for suffix in self.common_suffixes:
            if word.endswith(suffix) and len(word) - len(suffix) >= 3:
                return word[: -len(suffix)]

        return word

    def _analyze_search_intent(self, query: str) -> Dict:
        """
        Analyze search query to determine intent and extract key parameters.
        """
        intent = {
            "primary_category": None,
            "price_sensitivity": 0.5,  # Default: neutral
            "location_terms": [],
            "service_type": None,
            "sentiment": "neutral",
        }

        if not query:
            return intent

        # Convert to lowercase for case-insensitive matching
        lower_query = query.lower()

        # Check for price sensitivity
        if any(term in lower_query for term in ["cheap", "affordable", "budget", "inexpensive"]):
            intent["price_sensitivity"] = 0.8  # High price sensitivity
        elif any(term in lower_query for term in ["luxury", "premium", "high-end", "best"]):
            intent["price_sensitivity"] = 0.2  # Low price sensitivity (willing to pay more)

        # Check for service type hints
        if "home" in lower_query or "at home" in lower_query:
            intent["service_type"] = "in_home"
        elif "shop" in lower_query or "salon" in lower_query or "store" in lower_query:
            intent["service_type"] = "in_shop"

        # Detect location terms
        location_indicators = ["near", "nearby", "close to", "around"]
        for indicator in location_indicators:
            if indicator in lower_query:
                # Extract what comes after the indicator
                pos = lower_query.find(indicator) + len(indicator)
                remainder = lower_query[pos:].strip()
                words = remainder.split()
                if words:
                    # Take the next few words as a location reference
                    location_ref = " ".join(words[:3])
                    intent["location_terms"].append(location_ref)

        # Detect primary category (simplified)
        # In a real implementation, would use a more sophisticated
        # category detection system with a taxonomy
        common_categories = {
            "haircut": "hair",
            "hair": "hair",
            "nail": "nails",
            "massage": "spa",
            "facial": "spa",
            "spa": "spa",
            "beauty": "beauty",
            "makeup": "beauty",
            "skin": "skincare",
            "consultation": "medical",
            "doctor": "medical",
            "clinic": "medical",
            "dental": "dental",
            "teeth": "dental",
            "clean": "cleaning",
        }

        for term, category in common_categories.items():
            if term in lower_query:
                intent["primary_category"] = category
                break

        # Detect sentiment (simplified)
        positive_terms = ["best", "great", "excellent", "top", "recommended"]
        negative_terms = ["avoid", "bad", "worst", "cheap"]

        if any(term in lower_query for term in positive_terms):
            intent["sentiment"] = "positive"
        elif any(term in lower_query for term in negative_terms):
            intent["sentiment"] = "negative"

        return intent

    def _calculate_text_match(self, service: Dict, query_terms: set, search_intent: Dict) -> float:
        """
        Calculate text matching score between service and query.
        """
        # Get service text fields
        name = service.get("name", "").lower()
        description = service.get("description", "").lower()
        shop_name = service.get("shop_name", "").lower()
        category_name = service.get("category_name", "").lower()
        tags = service.get("tags", [])

        # Create a combined text string for matching
        service_text = f"{name} {description} {shop_name} {category_name}"
        service_text += " " + " ".join(tags)

        # Preprocess service text the same way as the query
        processed_text = self._preprocess_query(service_text)
        service_terms = set(processed_text.split())

        # Calculate term overlap
        if not query_terms:
            return 0.5  # Neutral score for empty query

        if not service_terms:
            return 0.0  # No match if service has no terms

        # Exact matches (full terms)
        exact_matches = query_terms.intersection(service_terms)
        exact_match_ratio = len(exact_matches) / len(query_terms)

        # Fuzzy matches if enabled
        fuzzy_match_ratio = 0.0
        if self.fuzzy_matching:
            fuzzy_matches = 0
            for query_term in query_terms:
                for service_term in service_terms:
                    # Check if query term is contained within service term
                    if query_term in service_term and query_term != service_term:
                        fuzzy_matches += 0.5  # Partial match
                        break

            fuzzy_match_ratio = fuzzy_matches / len(query_terms)

        # Weight by field importance
        field_weights = {}

        # Name matches are most important
        field_weights["name"] = 0
        for term in query_terms:
            if term in name:
                field_weights["name"] += 1

        # Category matches are also important
        field_weights["category"] = 0
        for term in query_terms:
            if term in category_name:
                field_weights["category"] += 1

        # Calculate final text match score
        # Heavily weight exact matches, but consider fuzzy matches too
        base_score = (exact_match_ratio * 0.8) + (fuzzy_match_ratio * 0.2)

        # Boost for name/category matches
        name_boost = min(1.0, field_weights["name"] / len(query_terms)) * 0.3
        category_boost = min(1.0, field_weights["category"] / len(query_terms)) * 0.2

        final_score = base_score + name_boost + category_boost

        # Cap at 1.0
        return min(1.0, final_score)

    def _calculate_category_match(
        self, service: Dict, search_intent: Dict, customer_data: Optional[Dict]
    ) -> float:
        """
        Calculate category match score based on intent and preferences.
        """
        # Get service category
        category_id = service.get("category_id")

        # If no category info available
        if not category_id:
            return 0.5  # Neutral score

        # Check if category matches intent
        intent_category = search_intent.get("primary_category")
        if intent_category:
            category_name = service.get("category_name", "").lower()
            if intent_category in category_name:
                return 1.0  # Perfect match with intent

        # If customer preferences available, check match
        if customer_data and "preferred_categories" in customer_data:
            preferred_categories = customer_data["preferred_categories"]
            if category_id in preferred_categories:
                return 0.9  # High match with customer preferences

        # If service type specified in intent, check match
        intent_service_type = search_intent.get("service_type")
        if intent_service_type:
            service_location = service.get("service_location")
            if service_location and service_location == intent_service_type:
                return 0.8  # Good match with service type intent
            elif service_location and service_location == "both":
                return 0.7  # Partial match with service type intent

        # Default score if no specific matches
        return 0.5

    def _calculate_rating_score(self, service: Dict) -> float:
        """
        Calculate score based on service rating.
        """
        rating = service.get("rating")

        if rating is None:
            return 0.5  # Neutral score if no rating

        # Convert rating to 0-1 scale (assuming 1-5 rating)
        normalized_rating = (rating - 1) / 4.0

        return normalized_rating

    def _calculate_price_score(self, service: Dict, price_sensitivity: float) -> float:
        """
        Calculate score based on price and price sensitivity.

        Higher price_sensitivity means customer prefers lower prices.
        """
        price = service.get("price")

        if price is None:
            return 0.5  # Neutral score if no price

        # For high price sensitivity, lower prices score higher
        # For low price sensitivity, price matters less

        # Normalize price (assuming typical range)
        # This would ideally use category-specific price ranges
        max_price = 1000  # Example maximum price in SAR
        normalized_price = min(1.0, price / max_price)

        if price_sensitivity >= 0.7:
            # High price sensitivity: prefer lowest price
            return 1.0 - normalized_price
        elif price_sensitivity <= 0.3:
            # Low price sensitivity: might prefer higher price (quality signal)
            return 0.5 + (normalized_price * 0.5)
        else:
            # Neutral: slight preference for lower prices
            return 1.0 - (normalized_price * 0.5)

    def _calculate_location_score(self, service: Dict, location_data: Dict) -> float:
        """
        Calculate score based on distance.
        """
        # Get location data
        customer_lat = location_data.get("latitude")
        customer_lng = location_data.get("longitude")

        shop_location = service.get("shop_location", {})
        shop_lat = shop_location.get("latitude")
        shop_lng = shop_location.get("longitude")

        # If location data missing, return neutral score
        if not customer_lat or not customer_lng or not shop_lat or not shop_lng:
            return 0.5

        # Calculate distance in kilometers
        distance_km = self._calculate_distance(customer_lat, customer_lng, shop_lat, shop_lng)

        # Convert distance to score (closer is better)
        # Using exponential decay function
        location_score = math.exp(-distance_km / 5.0)

        return location_score

    def _calculate_distance(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """
        Calculate distance between two points using Haversine formula.
        """
        from math import atan2, cos, radians, sin, sqrt

        # Earth radius in kilometers
        earth_radius = 6371.0

        # Convert latitude and longitude from degrees to radians
        lat1_rad = radians(float(lat1))
        lng1_rad = radians(float(lng1))
        lat2_rad = radians(float(lat2))
        lng2_rad = radians(float(lng2))

        # Haversine formula
        dlng = lng2_rad - lng1_rad
        dlat = lat2_rad - lat1_rad

        a = sin(dlat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlng / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        # Distance in kilometers
        distance = earth_radius * c

        return distance

    def _check_availability(self, service: Dict, date_str: str) -> bool:
        """
        Check if service is available on specified date.

        In a real implementation, this would query the availability
        system to check if there are free slots on that date.
        """
        # Check general availability flag
        is_available = service.get("is_available", True)

        if not is_available:
            return False

        # For this simplified version, assume service is available
        # unless specifically marked as unavailable for this date
        unavailable_dates = service.get("unavailable_dates", [])

        if date_str in unavailable_dates:
            return False

        return True

    def _apply_filters(self, service: Dict, filters: Dict) -> bool:
        """
        Apply filters to a service.
        Returns True if service passes all filters, False otherwise.
        """
        for field, value in filters.items():
            # Skip special filters
            if field == "available_only":
                continue

            # Handle range filters
            if field.endswith("_min") or field.endswith("_max"):
                base_field = field[:-4]  # Remove _min or _max suffix

                if base_field not in service:
                    return False

                service_value = service[base_field]

                if field.endswith("_min") and service_value < value:
                    return False

                if field.endswith("_max") and service_value > value:
                    return False

            # Handle multi-value filters (e.g., category_id=[1,2,3])
            elif isinstance(value, list):
                if field not in service or service[field] not in value:
                    return False

            # Handle simple equality filters
            elif field in service and service[field] != value:
                return False

        return True
