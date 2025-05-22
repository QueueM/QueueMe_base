# apps/rolesapp/serializers.py
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.authapp.models import User
from apps.authapp.serializers import UserLightSerializer
from apps.rolesapp.models import Permission, Role, RolePermissionLog, UserRole


class PermissionSerializer(serializers.ModelSerializer):
    """Serializer for Permission model"""

    resource_display = serializers.CharField(
        source="get_resource_display", read_only=True
    )
    action_display = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = Permission
        fields = [
            "id",
            "resource",
            "action",
            "code_name",
            "description",
            "resource_display",
            "action_display",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "code_name", "created_at", "updated_at"]


class RoleSerializer(serializers.ModelSerializer):
    """Serializer for Role model"""

    permissions = PermissionSerializer(many=True, read_only=True)
    permission_ids = serializers.ListField(
        child=serializers.UUIDField(), write_only=True, required=False
    )
    role_type_display = serializers.CharField(
        source="get_role_type_display", read_only=True
    )
    parent_name = serializers.CharField(source="parent.name", read_only=True)
    entity_name = serializers.SerializerMethodField()
    user_count = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = [
            "id",
            "name",
            "description",
            "role_type",
            "role_type_display",
            "permissions",
            "permission_ids",
            "content_type",
            "object_id",
            "entity_name",
            "parent",
            "parent_name",
            "weight",
            "is_active",
            "is_system",
            "user_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_system", "created_at", "updated_at"]

    def get_entity_name(self, obj):
        """Get the name of the associated entity"""
        if hasattr(obj, "entity") and obj.entity:
            return str(obj.entity)
        return None

    def get_user_count(self, obj):
        """Get the count of users with this role"""
        return obj.user_roles.count()

    def validate(self, data):
        """Custom validation logic"""
        # Ensure content_type and object_id are either both present or both absent
        content_type = data.get("content_type")
        object_id = data.get("object_id")

        if (content_type and not object_id) or (object_id and not content_type):
            raise serializers.ValidationError(
                _("Both content_type and object_id must be provided together")
            )

        # Validate entity exists if both content_type and object_id are provided
        if content_type and object_id:
            try:
                model_class = content_type.model_class()
                if not model_class.objects.filter(id=object_id).exists():
                    raise serializers.ValidationError(
                        _("Entity with the provided ID does not exist")
                    )
            except Exception as e:
                raise serializers.ValidationError(str(e))

        # Validate parent role exists and is compatible
        parent_id = data.get("parent")
        if parent_id:
            try:
                parent_role = Role.objects.get(id=parent_id)

                # Ensure no circular dependencies
                parent_chain = [parent_role]
                current = parent_role
                while current.parent:
                    if current.parent.id == data.get("id"):
                        raise serializers.ValidationError(
                            _("Circular dependency detected in role hierarchy")
                        )
                    current = current.parent
                    parent_chain.append(current)

                # Ensure compatible entity contexts
                if content_type and object_id:
                    if parent_role.content_type and parent_role.object_id:
                        if (
                            parent_role.content_type != content_type
                            or parent_role.object_id != object_id
                        ):
                            raise serializers.ValidationError(
                                _("Parent role must be for the same entity")
                            )
            except Role.DoesNotExist:
                raise serializers.ValidationError(_("Parent role does not exist"))

        return data

    def create(self, validated_data):
        """Create a new role with permissions"""
        permission_ids = validated_data.pop("permission_ids", [])
        with transaction.atomic():
            role = Role.objects.create(**validated_data)

            if permission_ids:
                permissions = Permission.objects.filter(id__in=permission_ids)
                role.permissions.set(permissions)

                # Log permission changes
                user = (
                    self.context["request"].user if "request" in self.context else None
                )
                for permission in permissions:
                    RolePermissionLog.objects.create(
                        role=role,
                        permission=permission,
                        action_type="add",
                        performed_by=user,
                    )

        return role

    def update(self, instance, validated_data):
        """Update an existing role with permissions"""
        permission_ids = validated_data.pop("permission_ids", None)
        with transaction.atomic():
            # Update role fields
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            # Update permissions if provided
            if permission_ids is not None:
                # Get old permissions for logging changes
                old_permissions = set(instance.permissions.all())
                new_permissions = set(Permission.objects.filter(id__in=permission_ids))

                # Find added and removed permissions
                added_permissions = new_permissions - old_permissions
                removed_permissions = old_permissions - new_permissions

                # Update permissions
                instance.permissions.set(new_permissions)

                # Log permission changes
                user = (
                    self.context["request"].user if "request" in self.context else None
                )
                for permission in added_permissions:
                    RolePermissionLog.objects.create(
                        role=instance,
                        permission=permission,
                        action_type="add",
                        performed_by=user,
                    )

                for permission in removed_permissions:
                    RolePermissionLog.objects.create(
                        role=instance,
                        permission=permission,
                        action_type="remove",
                        performed_by=user,
                    )

        return instance


class ContentTypeSerializer(serializers.ModelSerializer):
    """Serializer for ContentType model"""

    class Meta:
        model = ContentType
        fields = ["id", "app_label", "model"]


class RoleDetailSerializer(RoleSerializer):
    """Detailed serializer for Role with user information"""

    users = serializers.SerializerMethodField()

    class Meta(RoleSerializer.Meta):
        fields = RoleSerializer.Meta.fields + ["users"]

    def get_users(self, obj):
        """Get all users with this role"""
        user_roles = obj.user_roles.all()[:10]  # Limit to 10 users for performance
        return UserRoleSerializer(user_roles, many=True).data


class UserRoleSerializer(serializers.ModelSerializer):
    """Serializer for UserRole model"""

    user_detail = UserLightSerializer(source="user", read_only=True)
    role_detail = RoleSerializer(source="role", read_only=True)
    assigned_by_detail = UserLightSerializer(source="assigned_by", read_only=True)

    class Meta:
        model = UserRole
        fields = [
            "id",
            "user",
            "user_detail",
            "role",
            "role_detail",
            "assigned_at",
            "assigned_by",
            "assigned_by_detail",
            "is_primary",
        ]
        read_only_fields = ["id", "assigned_at"]

    def validate(self, data):
        """Custom validation for UserRole"""
        # Validate user exists
        user_id = data.get("user").id if data.get("user") else None
        if user_id:
            try:
                User.objects.get(id=user_id)
            except User.DoesNotExist:
                raise serializers.ValidationError({"user": _("User does not exist")})

        # Validate role exists
        role_id = data.get("role").id if data.get("role") else None
        if role_id:
            try:
                Role.objects.get(id=role_id)
            except Role.DoesNotExist:
                raise serializers.ValidationError({"role": _("Role does not exist")})

        # Check if this user role already exists
        if user_id and role_id:
            if UserRole.objects.filter(user_id=user_id, role_id=role_id).exists():
                if (
                    self.instance
                    and self.instance.user_id == user_id
                    and self.instance.role_id == role_id
                ):
                    # This is the same instance being updated
                    pass
                else:
                    raise serializers.ValidationError(
                        _("This user already has this role")
                    )

        return data


class RolePermissionLogSerializer(serializers.ModelSerializer):
    """Serializer for RolePermissionLog model"""

    role_detail = RoleSerializer(source="role", read_only=True)
    permission_detail = PermissionSerializer(source="permission", read_only=True)
    performed_by_detail = UserLightSerializer(source="performed_by", read_only=True)

    class Meta:
        model = RolePermissionLog
        fields = [
            "id",
            "role",
            "role_detail",
            "permission",
            "permission_detail",
            "action_type",
            "performed_by",
            "performed_by_detail",
            "timestamp",
        ]
        read_only_fields = ["id", "timestamp"]


class PermissionGroupSerializer(serializers.Serializer):
    """Grouped permissions by resource"""

    resource = serializers.CharField()
    resource_display = serializers.CharField()
    permissions = PermissionSerializer(many=True)
