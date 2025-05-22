from django.db import transaction

from apps.customersapp.models import FavoriteService, FavoriteShop, FavoriteSpecialist


class FavoritesService:
    """
    Service for managing customer favorites
    """

    @staticmethod
    def toggle_favorite_shop(customer, shop_id):
        """
        Toggle a shop's favorite status
        Returns (is_favorite, created)
        """
        from apps.shopapp.models import Shop

        try:
            # Check if already favorite
            existing = FavoriteShop.objects.filter(
                customer=customer, shop_id=shop_id
            ).first()

            if existing:
                # Remove from favorites
                existing.delete()
                return False, False

            # Add to favorites
            shop = Shop.objects.get(id=shop_id)
            FavoriteShop.objects.create(customer=customer, shop=shop)
            return True, True

        except Shop.DoesNotExist:
            raise ValueError("Shop not found")

    @staticmethod
    def toggle_favorite_specialist(customer, specialist_id):
        """
        Toggle a specialist's favorite status
        Returns (is_favorite, created)
        """
        from apps.specialistsapp.models import Specialist

        try:
            # Check if already favorite
            existing = FavoriteSpecialist.objects.filter(
                customer=customer, specialist_id=specialist_id
            ).first()

            if existing:
                # Remove from favorites
                existing.delete()
                return False, False

            # Add to favorites
            specialist = Specialist.objects.get(id=specialist_id)
            FavoriteSpecialist.objects.create(customer=customer, specialist=specialist)
            return True, True

        except Specialist.DoesNotExist:
            raise ValueError("Specialist not found")

    @staticmethod
    def toggle_favorite_service(customer, service_id):
        """
        Toggle a service's favorite status
        Returns (is_favorite, created)
        """
        from apps.serviceapp.models import Service

        try:
            # Check if already favorite
            existing = FavoriteService.objects.filter(
                customer=customer, service_id=service_id
            ).first()

            if existing:
                # Remove from favorites
                existing.delete()
                return False, False

            # Add to favorites
            service = Service.objects.get(id=service_id)
            FavoriteService.objects.create(customer=customer, service=service)
            return True, True

        except Service.DoesNotExist:
            raise ValueError("Service not found")

    @staticmethod
    def check_favorite_status(customer, entity_type, entity_id):
        """
        Check if an entity is favorited by the customer
        """
        if entity_type == "shop":
            return FavoriteShop.objects.filter(
                customer=customer, shop_id=entity_id
            ).exists()
        elif entity_type == "specialist":
            return FavoriteSpecialist.objects.filter(
                customer=customer, specialist_id=entity_id
            ).exists()
        elif entity_type == "service":
            return FavoriteService.objects.filter(
                customer=customer, service_id=entity_id
            ).exists()
        else:
            raise ValueError(f"Invalid entity type: {entity_type}")

    @staticmethod
    @transaction.atomic
    def bulk_add_favorites(customer, entity_type, entity_ids):
        """
        Add multiple entities to favorites at once
        """
        if entity_type == "shop":
            from apps.shopapp.models import Shop

            # Filter valid shop IDs
            valid_shops = Shop.objects.filter(id__in=entity_ids)

            # Get existing favorites to avoid duplicates
            existing = set(
                FavoriteShop.objects.filter(
                    customer=customer, shop_id__in=entity_ids
                ).values_list("shop_id", flat=True)
            )

            # Create new favorites
            new_favorites = []
            for shop in valid_shops:
                if shop.id not in existing:
                    new_favorites.append(FavoriteShop(customer=customer, shop=shop))

            # Bulk create
            if new_favorites:
                FavoriteShop.objects.bulk_create(new_favorites)

            return len(new_favorites)

        elif entity_type == "specialist":
            from apps.specialistsapp.models import Specialist

            # Filter valid specialist IDs
            valid_specialists = Specialist.objects.filter(id__in=entity_ids)

            # Get existing favorites to avoid duplicates
            existing = set(
                FavoriteSpecialist.objects.filter(
                    customer=customer, specialist_id__in=entity_ids
                ).values_list("specialist_id", flat=True)
            )

            # Create new favorites
            new_favorites = []
            for specialist in valid_specialists:
                if specialist.id not in existing:
                    new_favorites.append(
                        FavoriteSpecialist(customer=customer, specialist=specialist)
                    )

            # Bulk create
            if new_favorites:
                FavoriteSpecialist.objects.bulk_create(new_favorites)

            return len(new_favorites)

        elif entity_type == "service":
            from apps.serviceapp.models import Service

            # Filter valid service IDs
            valid_services = Service.objects.filter(id__in=entity_ids)

            # Get existing favorites to avoid duplicates
            existing = set(
                FavoriteService.objects.filter(
                    customer=customer, service_id__in=entity_ids
                ).values_list("service_id", flat=True)
            )

            # Create new favorites
            new_favorites = []
            for service in valid_services:
                if service.id not in existing:
                    new_favorites.append(
                        FavoriteService(customer=customer, service=service)
                    )

            # Bulk create
            if new_favorites:
                FavoriteService.objects.bulk_create(new_favorites)

            return len(new_favorites)

        else:
            raise ValueError(f"Invalid entity type: {entity_type}")
