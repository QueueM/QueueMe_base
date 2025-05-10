from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.utils.translation import gettext_lazy as _

from apps.specialistsapp.models import PortfolioItem, Specialist


class PortfolioService:
    """Service for managing specialist portfolios"""

    def get_portfolio_items(self, specialist_id, category_id=None, service_id=None):
        """
        Get portfolio items for a specialist with optional filtering.

        Args:
            specialist_id: UUID of the specialist
            category_id: Optional UUID of category to filter by
            service_id: Optional UUID of service to filter by

        Returns:
            QuerySet of PortfolioItem objects
        """
        queryset = PortfolioItem.objects.filter(
            specialist_id=specialist_id
        ).select_related("service", "category")

        if category_id:
            queryset = queryset.filter(category_id=category_id)

        if service_id:
            queryset = queryset.filter(service_id=service_id)

        return queryset.order_by("-is_featured", "-created_at")

    def create_portfolio_item(self, specialist_id, data, image=None):
        """
        Create a new portfolio item for a specialist.

        Args:
            specialist_id: UUID of the specialist
            data: Dictionary containing portfolio item data
            image: Optional uploaded image file

        Returns:
            Created PortfolioItem object
        """
        specialist = Specialist.objects.get(id=specialist_id)

        # Check portfolio item limit
        if specialist.portfolio.count() >= 20:
            raise ValidationError(_("Maximum number of portfolio items reached."))

        # Create portfolio item
        portfolio_item = PortfolioItem(
            specialist=specialist,
            title=data.get("title"),
            description=data.get("description", ""),
            service_id=data.get("service_id"),
            category_id=data.get("category_id"),
            is_featured=data.get("is_featured", False),
        )

        # Handle image upload
        if image:
            # Generate path and filename
            filename = f"{specialist_id}_{image.name}"
            path = f"specialists/portfolio/{filename}"

            # Save image to storage
            portfolio_item.image.save(path, image)

        portfolio_item.save()
        return portfolio_item

    def update_portfolio_item(self, portfolio_item_id, data, image=None):
        """
        Update an existing portfolio item.

        Args:
            portfolio_item_id: UUID of the portfolio item
            data: Dictionary containing updated portfolio item data
            image: Optional new uploaded image file

        Returns:
            Updated PortfolioItem object
        """
        portfolio_item = PortfolioItem.objects.get(id=portfolio_item_id)

        # Update fields
        if "title" in data:
            portfolio_item.title = data["title"]

        if "description" in data:
            portfolio_item.description = data["description"]

        if "service_id" in data:
            portfolio_item.service_id = data["service_id"]

        if "category_id" in data:
            portfolio_item.category_id = data["category_id"]

        if "is_featured" in data:
            portfolio_item.is_featured = data["is_featured"]

        # Handle image upload
        if image:
            # Delete old image if exists
            if portfolio_item.image:
                try:
                    default_storage.delete(portfolio_item.image.path)
                except Exception:
                    pass

            # Generate path and filename
            filename = f"{portfolio_item.specialist.id}_{image.name}"
            path = f"specialists/portfolio/{filename}"

            # Save new image
            portfolio_item.image.save(path, image)

        portfolio_item.save()
        return portfolio_item

    def delete_portfolio_item(self, portfolio_item_id):
        """
        Delete a portfolio item.

        Args:
            portfolio_item_id: UUID of the portfolio item

        Returns:
            Boolean indicating success
        """
        portfolio_item = PortfolioItem.objects.get(id=portfolio_item_id)

        # Delete image from storage
        if portfolio_item.image:
            try:
                default_storage.delete(portfolio_item.image.path)
            except Exception:
                pass

        portfolio_item.delete()
        return True

    def toggle_portfolio_item_feature(self, portfolio_item_id):
        """
        Toggle the featured status of a portfolio item.

        Args:
            portfolio_item_id: UUID of the portfolio item

        Returns:
            Updated PortfolioItem object
        """
        portfolio_item = PortfolioItem.objects.get(id=portfolio_item_id)
        portfolio_item.is_featured = not portfolio_item.is_featured
        portfolio_item.save()
        return portfolio_item

    def like_portfolio_item(self, portfolio_item_id):
        """
        Increment like count for a portfolio item.

        Args:
            portfolio_item_id: UUID of the portfolio item

        Returns:
            Updated PortfolioItem object
        """
        portfolio_item = PortfolioItem.objects.get(id=portfolio_item_id)
        portfolio_item.likes_count += 1
        portfolio_item.save(update_fields=["likes_count"])
        return portfolio_item

    def get_featured_portfolio_items(self, specialist_id, limit=5):
        """
        Get featured portfolio items for a specialist.

        Args:
            specialist_id: UUID of the specialist
            limit: Maximum number of items to return

        Returns:
            QuerySet of PortfolioItem objects
        """
        return (
            PortfolioItem.objects.filter(specialist_id=specialist_id, is_featured=True)
            .select_related("service", "category")
            .order_by("-created_at")[:limit]
        )

    def get_popular_portfolio_items(self, specialist_id, limit=5):
        """
        Get most popular portfolio items for a specialist.

        Args:
            specialist_id: UUID of the specialist
            limit: Maximum number of items to return

        Returns:
            QuerySet of PortfolioItem objects
        """
        return (
            PortfolioItem.objects.filter(specialist_id=specialist_id)
            .select_related("service", "category")
            .order_by("-likes_count", "-created_at")[:limit]
        )
