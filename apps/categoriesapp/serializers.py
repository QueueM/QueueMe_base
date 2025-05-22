from django.utils.translation import get_language
from rest_framework import serializers

from core.localization.translator import get_translated_field

from .models import Category, CategoryRelation


# Create simplified serializer for Category model
class CategorySimpleSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for Category model with minimal fields.
    Used by other apps that need basic category information.
    """

    class Meta:
        model = Category
        fields = ("id", "name", "icon")
        read_only_fields = fields


class CategoryRelationSerializer(serializers.ModelSerializer):
    """
    Serializer for category relations
    """

    to_category_name = serializers.SerializerMethodField()

    class Meta:
        model = CategoryRelation
        fields = ["id", "to_category", "to_category_name", "relation_type", "weight"]

    def get_to_category_name(self, obj):
        lang = get_language()
        if lang == "ar":
            return obj.to_category.name_ar
        return obj.to_category.name_en


class ChildCategorySerializer(serializers.ModelSerializer):
    """
    Serializer for child categories (used in parent category serializer)
    """

    name = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    service_count = serializers.ReadOnlyField()
    specialist_count = serializers.ReadOnlyField()

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "icon",
            "image",
            "is_active",
            "is_featured",
            "position",
            "service_count",
            "specialist_count",
        ]

    def get_name(self, obj):
        return get_translated_field(obj, "name")

    def get_description(self, obj):
        return get_translated_field(obj, "description")


class CategorySerializer(serializers.ModelSerializer):
    """
    Main category serializer with optional children inclusion
    """

    name = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()
    parent_name = serializers.SerializerMethodField()
    service_count = serializers.ReadOnlyField()
    specialist_count = serializers.ReadOnlyField()
    related_categories = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "icon",
            "image",
            "parent",
            "parent_name",
            "children",
            "is_active",
            "is_featured",
            "position",
            "service_count",
            "specialist_count",
            "related_categories",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "slug",
            "service_count",
            "specialist_count",
            "created_at",
            "updated_at",
        ]

    def get_name(self, obj):
        return get_translated_field(obj, "name")

    def get_description(self, obj):
        return get_translated_field(obj, "description")

    def get_parent_name(self, obj):
        if obj.parent:
            lang = get_language()
            if lang == "ar":
                return obj.parent.name_ar
            return obj.parent.name_en
        return None

    def get_children(self, obj):
        # Only get children for parent categories
        if obj.parent is None:
            children = obj.children.filter(is_active=True).order_by("position")
            return ChildCategorySerializer(
                children, many=True, context=self.context
            ).data
        return []

    def get_related_categories(self, obj):
        # Get related categories through CategoryRelation
        relations = CategoryRelation.objects.filter(from_category=obj).order_by(
            "-weight"
        )
        return CategoryRelationSerializer(
            relations, many=True, context=self.context
        ).data


class CategoryListSerializer(serializers.ModelSerializer):
    """
    Simplified category serializer for list views
    """

    name = serializers.SerializerMethodField()
    child_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "slug",
            "icon",
            "parent",
            "is_active",
            "child_count",
            "position",
        ]

    def get_name(self, obj):
        return get_translated_field(obj, "name")

    def get_child_count(self, obj):
        if obj.parent is None:
            return obj.children.count()
        return 0


class CategoryHierarchySerializer(serializers.ModelSerializer):
    """
    Recursive serializer for fetching complete category hierarchies
    Used for building category trees
    """

    name = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()
    service_count = serializers.ReadOnlyField()

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "slug",
            "icon",
            "children",
            "is_active",
            "position",
            "service_count",
        ]

    def get_name(self, obj):
        return get_translated_field(obj, "name")

    def get_children(self, obj):
        # Recursively include children
        children = obj.children.filter(is_active=True).order_by("position")
        return CategoryHierarchySerializer(
            children, many=True, context=self.context
        ).data


class CategoryCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating/updating categories with multilingual support
    """

    class Meta:
        model = Category
        fields = [
            "name",
            "name_en",
            "name_ar",
            "description",
            "description_en",
            "description_ar",
            "parent",
            "icon",
            "image",
            "is_active",
            "is_featured",
            "position",
        ]

    def validate(self, data):
        # Validate that we don't create circular dependencies
        parent = data.get("parent")
        instance = self.instance

        if parent and instance and instance.id == parent.id:
            raise serializers.ValidationError(
                {"parent": "A category cannot be its own parent."}
            )

        if parent and instance:
            # Check if this would create a circular reference in the hierarchy
            category_hierarchy = [parent]
            current = parent

            while current.parent:
                if current.parent.id == instance.id:
                    raise serializers.ValidationError(
                        {
                            "parent": "This would create a circular reference in the category hierarchy."
                        }
                    )
                category_hierarchy.append(current.parent)
                current = current.parent

        # Enforce name_en, name_ar based on name if not provided
        if "name" in data:
            if "name_en" not in data or not data["name_en"]:
                data["name_en"] = data["name"]
            if "name_ar" not in data or not data["name_ar"]:
                data["name_ar"] = data["name"]

        return data


class CategoryRelationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoryRelation
        fields = ["from_category", "to_category", "relation_type", "weight"]

    def validate(self, data):
        # Prevent self-relations
        if data["from_category"] == data["to_category"]:
            raise serializers.ValidationError(
                {"to_category": "A category cannot be related to itself."}
            )

        # Check if this relation already exists
        if CategoryRelation.objects.filter(
            from_category=data["from_category"],
            to_category=data["to_category"],
            relation_type=data["relation_type"],
        ).exists():
            raise serializers.ValidationError(
                {"non_field_errors": "This relation already exists."}
            )

        return data


CategorySimpleSerializer = CategorySerializer
CategoryLightSerializer = CategoryListSerializer
