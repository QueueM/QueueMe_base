import logging

from django.core.cache import cache
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.utils.text import slugify

from .models import Category, CategoryRelation

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Category)
def ensure_category_slug(sender, instance, **kwargs):
    """
    Ensure category has a slug before saving
    """
    if not instance.slug:
        # Generate slug from name if not provided
        slug = slugify(instance.name, allow_unicode=True)

        # Check if the slug is unique
        original_slug = slug
        counter = 1

        while Category.objects.filter(slug=slug).exclude(id=instance.id).exists():
            # If slug already exists, append a counter
            slug = f"{original_slug}-{counter}"
            counter += 1

        instance.slug = slug


@receiver(post_save, sender=Category)
def clear_category_cache(sender, instance, **kwargs):
    """
    Clear category-related caches when a category is created or updated
    """
    try:
        # Clear specific category cache
        cache.delete(f"category_{instance.id}")
        cache.delete(f"category_slug_{instance.slug}")

        # Clear related caches
        cache.delete("parent_categories_True")
        cache.delete("parent_categories_False")
        cache.delete("category_hierarchy")

        # Clear parent-child relationship caches
        if instance.parent:
            cache.delete(f"child_categories_{instance.parent.id}_True")
            cache.delete(f"child_categories_{instance.parent.id}_False")
        else:
            # If it's a parent category or its parent status changed
            cache.delete("parent_categories_True")
            cache.delete("parent_categories_False")

        # Clear related caches for category trees
        cache.delete("category_tree_True")
        cache.delete("category_tree_False")

        logger.debug(f"Cleared cache for category {instance.id}")
    except Exception as e:
        logger.error(f"Error clearing category cache: {str(e)}")


@receiver(post_delete, sender=Category)
def clear_category_cache_on_delete(sender, instance, **kwargs):
    """
    Clear category-related caches when a category is deleted
    """
    try:
        # Clear specific category cache
        cache.delete(f"category_{instance.id}")
        cache.delete(f"category_slug_{instance.slug}")

        # Clear related caches
        cache.delete("parent_categories_True")
        cache.delete("parent_categories_False")
        cache.delete("category_hierarchy")

        # Clear parent-child relationship caches
        if instance.parent:
            cache.delete(f"child_categories_{instance.parent.id}_True")
            cache.delete(f"child_categories_{instance.parent.id}_False")

        # Clear related caches for category trees
        cache.delete("category_tree_True")
        cache.delete("category_tree_False")

        logger.debug(f"Cleared cache for deleted category {instance.id}")
    except Exception as e:
        logger.error(f"Error clearing category cache on delete: {str(e)}")


@receiver(post_save, sender=CategoryRelation)
def clear_relation_cache(sender, instance, **kwargs):
    """
    Clear relation-specific caches when a category relation is created or updated
    """
    try:
        # Clear related categories cache
        cache.delete(f"related_categories_{instance.from_category.id}")

        logger.debug(f"Cleared cache for category relation {instance.id}")
    except Exception as e:
        logger.error(f"Error clearing relation cache: {str(e)}")


@receiver(post_delete, sender=CategoryRelation)
def clear_relation_cache_on_delete(sender, instance, **kwargs):
    """
    Clear relation-specific caches when a category relation is deleted
    """
    try:
        # Clear related categories cache
        cache.delete(f"related_categories_{instance.from_category.id}")

        logger.debug(f"Cleared cache for deleted category relation {instance.id}")
    except Exception as e:
        logger.error(f"Error clearing relation cache on delete: {str(e)}")
