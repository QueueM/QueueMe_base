from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Category, CategoryRelation


class ChildCategoryInline(admin.TabularInline):
    """
    Inline admin for child categories
    """

    model = Category
    fields = ("name", "name_en", "name_ar", "slug", "is_active", "position")
    readonly_fields = ("slug",)
    extra = 1
    verbose_name = _("Child Category")
    verbose_name_plural = _("Child Categories")
    fk_name = "parent"
    show_change_link = True


class CategoryRelationInline(admin.TabularInline):
    """
    Inline admin for category relations
    """

    model = CategoryRelation
    fields = ("to_category", "relation_type", "weight")
    extra = 1
    verbose_name = _("Related Category")
    verbose_name_plural = _("Related Categories")
    fk_name = "from_category"


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """
    Admin configuration for the Category model
    """

    list_display = (
        "name",
        "slug",
        "is_parent_category",
        "parent_name",
        "children_count",
        "is_active",
        "is_featured",
        "position",
        "created_at",
    )
    list_filter = ("is_active", "is_featured", "parent")
    search_fields = ("name", "name_en", "name_ar", "slug", "description")
    readonly_fields = ("slug", "created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("name", "slug", "parent")}),
        (
            _("Content"),
            {
                "fields": (
                    ("name_en", "name_ar"),
                    "description",
                    ("description_en", "description_ar"),
                )
            },
        ),
        (_("Media"), {"fields": ("icon", "image")}),
        (_("Settings"), {"fields": ("is_active", "is_featured", "position")}),
        (_("Metadata"), {"fields": ("created_at", "updated_at")}),
    )
    inlines = [ChildCategoryInline, CategoryRelationInline]

    def is_parent_category(self, obj):
        """Display whether this is a parent category"""
        return obj.parent is None

    is_parent_category.boolean = True
    is_parent_category.short_description = _("Parent Category")

    def parent_name(self, obj):
        """Display parent name if this is a child category"""
        if obj.parent:
            return obj.parent.name
        return "—"

    parent_name.short_description = _("Parent")

    def children_count(self, obj):
        """Display number of child categories"""
        return obj.children.count()

    children_count.short_description = _("Children")

    def get_queryset(self, request):
        """Optimize query with parent prefetching"""
        return super().get_queryset(request).select_related("parent")

    def get_inlines(self, request, obj):
        """Only show child categories inline for parent categories"""
        if obj and obj.parent is None:
            return [ChildCategoryInline, CategoryRelationInline]
        return [CategoryRelationInline]


@admin.register(CategoryRelation)
class CategoryRelationAdmin(admin.ModelAdmin):
    """
    Admin configuration for the CategoryRelation model
    """

    list_display = ("from_category", "to_category", "relation_type", "weight")
    list_filter = ("relation_type",)
    search_fields = ("from_category__name", "to_category__name")
    raw_id_fields = ("from_category", "to_category")

    def get_queryset(self, request):
        """Optimize query with related prefetching"""
        return (
            super().get_queryset(request).select_related("from_category", "to_category")
        )
