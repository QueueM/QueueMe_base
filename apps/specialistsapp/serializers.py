from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.categoriesapp.models import Category
from apps.employeeapp.models import Employee
from apps.serviceapp.models import Service
from apps.specialistsapp.models import (
    PortfolioItem,
    Specialist,
    SpecialistService,
    SpecialistWorkingHours,
)


class SpecialistWorkingHoursSerializer(serializers.ModelSerializer):
    weekday_name = serializers.SerializerMethodField()

    class Meta:
        model = SpecialistWorkingHours
        fields = ("id", "weekday", "weekday_name", "from_hour", "to_hour", "is_off")

    def get_weekday_name(self, obj):
        return obj.get_weekday_display()


class PortfolioItemSerializer(serializers.ModelSerializer):
    service_name = serializers.ReadOnlyField(source="service.name", default="")
    category_name = serializers.ReadOnlyField(source="category.name", default="")
    thumbnail_url = serializers.ReadOnlyField()

    class Meta:
        model = PortfolioItem
        fields = (
            "id",
            "title",
            "description",
            "image",
            "thumbnail_url",
            "service",
            "service_name",
            "category",
            "category_name",
            "likes_count",
            "is_featured",
            "created_at",
        )
        read_only_fields = ("likes_count", "created_at")

    def validate(self, attrs):
        """Validate that specialist doesn't exceed max portfolio items"""
        specialist = self.context.get("specialist")
        if specialist and not self.instance:  # Only on create
            if specialist.portfolio.count() >= 20:  # Max portfolio items
                raise serializers.ValidationError(
                    _("Maximum number of portfolio items reached.")
                )
        return attrs


class SpecialistServiceSerializer(serializers.ModelSerializer):
    service_name = serializers.ReadOnlyField(source="service.name")
    service_price = serializers.ReadOnlyField(source="service.price")
    service_duration = serializers.ReadOnlyField(source="service.duration")
    effective_duration = serializers.ReadOnlyField(source="get_effective_duration")
    category_name = serializers.SerializerMethodField()

    class Meta:
        model = SpecialistService
        fields = (
            "id",
            "service",
            "service_name",
            "service_price",
            "service_duration",
            "is_primary",
            "proficiency_level",
            "custom_duration",
            "effective_duration",
            "booking_count",
            "category_name",
        )
        read_only_fields = ("booking_count",)

    def get_category_name(self, obj):
        if obj.service.category:
            return obj.service.category.name
        return ""


class SpecialistListSerializer(serializers.ModelSerializer):
    first_name = serializers.ReadOnlyField(source="employee.first_name")
    last_name = serializers.ReadOnlyField(source="employee.last_name")
    shop_id = serializers.ReadOnlyField(source="employee.shop.id")
    shop_name = serializers.ReadOnlyField(source="employee.shop.name")
    profile_image = serializers.ReadOnlyField(
        source="employee.profile_image.url", default=None
    )
    top_services = serializers.SerializerMethodField()
    expertise_categories = serializers.SerializerMethodField()

    class Meta:
        model = Specialist
        fields = (
            "id",
            "first_name",
            "last_name",
            "profile_image",
            "bio",
            "experience_years",
            "experience_level",
            "shop_id",
            "shop_name",
            "is_verified",
            "avg_rating",
            "total_bookings",
            "top_services",
            "expertise_categories",
        )

    def get_top_services(self, obj):
        top_services = obj.specialist_services.filter(is_primary=True).order_by(
            "-booking_count"
        )[:3]

        return [
            {
                "id": service.service.id,
                "name": service.service.name,
                "category": (
                    service.service.category.name if service.service.category else None
                ),
            }
            for service in top_services
        ]

    def get_expertise_categories(self, obj):
        return [
            {"id": category.id, "name": category.name}
            for category in obj.expertise.all()[:5]
        ]


class SpecialistDetailSerializer(serializers.ModelSerializer):
    first_name = serializers.ReadOnlyField(source="employee.first_name")
    last_name = serializers.ReadOnlyField(source="employee.last_name")
    phone_number = serializers.ReadOnlyField(source="employee.user.phone_number")
    email = serializers.ReadOnlyField(source="employee.email")
    profile_image = serializers.ReadOnlyField(
        source="employee.profile_image.url", default=None
    )
    shop_id = serializers.ReadOnlyField(source="employee.shop.id")
    shop_name = serializers.ReadOnlyField(source="employee.shop.name")
    services = SpecialistServiceSerializer(
        source="specialist_services", many=True, read_only=True
    )
    working_hours = SpecialistWorkingHoursSerializer(many=True, read_only=True)
    portfolio_items = PortfolioItemSerializer(
        source="portfolio", many=True, read_only=True
    )
    expertise_categories = serializers.SerializerMethodField()

    class Meta:
        model = Specialist
        fields = (
            "id",
            "first_name",
            "last_name",
            "phone_number",
            "email",
            "profile_image",
            "bio",
            "experience_years",
            "experience_level",
            "shop_id",
            "shop_name",
            "is_verified",
            "verified_at",
            "avg_rating",
            "total_bookings",
            "services",
            "working_hours",
            "portfolio_items",
            "expertise_categories",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "verified_at",
            "avg_rating",
            "total_bookings",
            "created_at",
            "updated_at",
        )

    def get_expertise_categories(self, obj):
        return [
            {"id": category.id, "name": category.name}
            for category in obj.expertise.all()
        ]


class SpecialistCreateSerializer(serializers.ModelSerializer):
    employee_id = serializers.UUIDField(required=True)
    expertise_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, write_only=True
    )
    service_ids = serializers.ListField(
        child=serializers.UUIDField(), required=True, write_only=True
    )
    working_hours = SpecialistWorkingHoursSerializer(many=True, required=False)

    class Meta:
        model = Specialist
        fields = (
            "employee_id",
            "bio",
            "experience_years",
            "experience_level",
            "expertise_ids",
            "service_ids",
            "working_hours",
        )

    def validate_employee_id(self, value):
        """Validate employee exists and doesn't already have a specialist profile"""
        try:
            employee = Employee.objects.get(id=value)

            # Check if employee already has a specialist profile
            if hasattr(employee, "specialist"):
                raise serializers.ValidationError(
                    _("Employee already has a specialist profile.")
                )

            # Ensure employee is active
            if not employee.is_active:
                raise serializers.ValidationError(
                    _("Cannot create specialist profile for inactive employee.")
                )

            return value
        except Employee.DoesNotExist:
            raise serializers.ValidationError(
                _("Employee with this ID does not exist.")
            )

    def validate_service_ids(self, value):
        """Validate services exist and belong to the shop"""
        employee_id = self.initial_data.get("employee_id")
        if not employee_id:
            return value

        try:
            employee = Employee.objects.get(id=employee_id)
            shop = employee.shop

            invalid_services = []
            for service_id in value:
                try:
                    service = Service.objects.get(id=service_id)
                    if service.shop.id != shop.id:
                        invalid_services.append(str(service_id))
                except Service.DoesNotExist:
                    invalid_services.append(str(service_id))

            if invalid_services:
                raise serializers.ValidationError(
                    _(
                        "The following services do not exist or don't belong to the shop: {}"
                    ).format(", ".join(invalid_services))
                )

            return value
        except Employee.DoesNotExist:
            # This is handled in validate_employee_id
            return value

    def validate_expertise_ids(self, value):
        """Validate categories exist"""
        invalid_categories = []
        for category_id in value:
            if not Category.objects.filter(id=category_id).exists():
                invalid_categories.append(str(category_id))

        if invalid_categories:
            raise serializers.ValidationError(
                _("The following categories do not exist: {}").format(
                    ", ".join(invalid_categories)
                )
            )

        return value

    @transaction.atomic
    def create(self, validated_data):
        """Create specialist with services and working hours"""
        employee_id = validated_data.pop("employee_id")
        service_ids = validated_data.pop("service_ids", [])
        expertise_ids = validated_data.pop("expertise_ids", [])
        working_hours_data = validated_data.pop("working_hours", [])

        employee = Employee.objects.get(id=employee_id)
        shop = employee.shop

        # Create specialist
        specialist = Specialist.objects.create(employee=employee, **validated_data)

        # Add expertise categories
        if expertise_ids:
            categories = Category.objects.filter(id__in=expertise_ids)
            specialist.expertise.set(categories)

        # Add services
        services = Service.objects.filter(id__in=service_ids, shop=shop)
        for service in services:
            SpecialistService.objects.create(
                specialist=specialist,
                service=service,
                is_primary=service == services.first(),  # First service is primary
            )

        # Create working hours (default or provided)
        if working_hours_data:
            for hours_data in working_hours_data:
                SpecialistWorkingHours.objects.create(
                    specialist=specialist, **hours_data
                )
        else:
            # Create default working hours (9AM-5PM, Sun-Thu, Friday off)
            from apps.specialistsapp.constants import (
                DEFAULT_END_HOUR,
                DEFAULT_START_HOUR,
            )

            for day in range(7):  # 0=Sunday, 6=Saturday
                SpecialistWorkingHours.objects.create(
                    specialist=specialist,
                    weekday=day,
                    from_hour=DEFAULT_START_HOUR,
                    to_hour=DEFAULT_END_HOUR,
                    is_off=(day == 5),  # Friday off by default
                )

        # If shop is verified, auto-verify specialist
        if shop.is_verified:
            specialist.is_verified = True
            specialist.verified_at = shop.verification_date
            specialist.save()

        return specialist


class SpecialistUpdateSerializer(serializers.ModelSerializer):
    expertise_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, write_only=True
    )

    class Meta:
        model = Specialist
        fields = ("bio", "experience_years", "experience_level", "expertise_ids")

    def validate_expertise_ids(self, value):
        """Validate categories exist"""
        invalid_categories = []
        for category_id in value:
            if not Category.objects.filter(id=category_id).exists():
                invalid_categories.append(str(category_id))

        if invalid_categories:
            raise serializers.ValidationError(
                _("The following categories do not exist: {}").format(
                    ", ".join(invalid_categories)
                )
            )

        return value

    @transaction.atomic
    def update(self, instance, validated_data):
        """Update specialist with expertise"""
        expertise_ids = validated_data.pop("expertise_ids", None)

        # Update specialist fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update expertise categories if provided
        if expertise_ids is not None:
            categories = Category.objects.filter(id__in=expertise_ids)
            instance.expertise.set(categories)

        return instance


class SpecialistServiceCreateSerializer(serializers.ModelSerializer):
    service_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = SpecialistService
        fields = ("service_id", "is_primary", "proficiency_level", "custom_duration")

    def validate_service_id(self, value):
        """Validate service exists and belongs to the specialist's shop"""
        specialist = self.context.get("specialist")
        if not specialist:
            raise serializers.ValidationError(_("Specialist context is required."))

        shop = specialist.employee.shop

        try:
            # Commenting out unused variable - fix for F841
            Service.objects.get(id=value, shop=shop)
            return value
        except Service.DoesNotExist:
            raise serializers.ValidationError(
                _("Service does not exist or doesn't belong to the shop.")
            )

    def validate(self, attrs):
        """Check if this service is already assigned to the specialist"""
        specialist = self.context.get("specialist")
        service_id = attrs.get("service_id")

        if specialist and service_id:
            if SpecialistService.objects.filter(
                specialist=specialist, service_id=service_id
            ).exists():
                raise serializers.ValidationError(
                    _("This service is already assigned to the specialist.")
                )

        return attrs

    def create(self, validated_data):
        """Create specialist service"""
        specialist = self.context.get("specialist")
        service_id = validated_data.pop("service_id")
        service = Service.objects.get(id=service_id)

        specialist_service = SpecialistService.objects.create(
            specialist=specialist, service=service, **validated_data
        )

        return specialist_service


class SpecialistServiceUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpecialistService
        fields = ("is_primary", "proficiency_level", "custom_duration")

    def update(self, instance, validated_data):
        """Update specialist service"""
        # Make other services non-primary if this one is being set as primary
        if validated_data.get("is_primary", False) and not instance.is_primary:
            SpecialistService.objects.filter(
                specialist=instance.specialist, is_primary=True
            ).update(is_primary=False)

        return super().update(instance, validated_data)


class SpecialistWorkingHoursCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpecialistWorkingHours
        fields = ("weekday", "from_hour", "to_hour", "is_off")

    def validate(self, attrs):
        """Validate working hours are within shop hours"""
        specialist = self.context.get("specialist")
        if not specialist:
            raise serializers.ValidationError(_("Specialist context is required."))

        weekday = attrs.get("weekday")
        from_hour = attrs.get("from_hour")
        to_hour = attrs.get("to_hour")

        if weekday is not None and from_hour and to_hour:
            shop = specialist.employee.shop
            shop_hours = shop.hours.filter(weekday=weekday).first()

            if not shop_hours:
                raise serializers.ValidationError(
                    _("Shop has no hours defined for this day.")
                )

            if shop_hours.is_closed:
                raise serializers.ValidationError(_("Shop is closed on this day."))

            if from_hour < shop_hours.from_hour:
                raise serializers.ValidationError(
                    _("Working hours cannot start before shop hours.")
                )

            if to_hour > shop_hours.to_hour:
                raise serializers.ValidationError(
                    _("Working hours cannot end after shop hours.")
                )

            if from_hour >= to_hour:
                raise serializers.ValidationError(
                    _("Start time must be before end time.")
                )

        return attrs


class PortfolioItemCreateSerializer(serializers.ModelSerializer):
    service_id = serializers.UUIDField(required=False, allow_null=True, write_only=True)
    category_id = serializers.UUIDField(
        required=False, allow_null=True, write_only=True
    )

    class Meta:
        model = PortfolioItem
        fields = (
            "title",
            "description",
            "image",
            "service_id",
            "category_id",
            "is_featured",
        )

    def validate(self, attrs):
        """Validate portfolio item creation"""
        specialist = self.context.get("specialist")

        # Check if maximum number of portfolio items reached
        if not self.instance and specialist:
            current_count = specialist.portfolio.count()
            if current_count >= 20:  # Max portfolio items limit
                raise serializers.ValidationError(
                    _("Maximum number of portfolio items reached.")
                )

        # Validate service
        service_id = attrs.pop("service_id", None)
        if service_id:
            try:
                shop = specialist.employee.shop
                service = Service.objects.get(id=service_id, shop=shop)
                attrs["service"] = service
            except Service.DoesNotExist:
                raise serializers.ValidationError(
                    {
                        "service_id": _(
                            "Service does not exist or doesn't belong to the shop."
                        )
                    }
                )

        # Validate category
        category_id = attrs.pop("category_id", None)
        if category_id:
            try:
                category = Category.objects.get(id=category_id)
                attrs["category"] = category
            except Category.DoesNotExist:
                raise serializers.ValidationError(
                    {"category_id": _("Category does not exist.")}
                )

        return attrs

    def create(self, validated_data):
        """Create portfolio item"""
        specialist = self.context.get("specialist")
        return PortfolioItem.objects.create(specialist=specialist, **validated_data)


class PortfolioItemUpdateSerializer(serializers.ModelSerializer):
    service_id = serializers.UUIDField(required=False, allow_null=True, write_only=True)
    category_id = serializers.UUIDField(
        required=False, allow_null=True, write_only=True
    )

    class Meta:
        model = PortfolioItem
        fields = (
            "title",
            "description",
            "image",
            "service_id",
            "category_id",
            "is_featured",
        )

    def validate(self, attrs):
        """Validate portfolio item update"""
        specialist = self.instance.specialist

        # Validate service
        service_id = attrs.pop("service_id", None)
        if service_id:
            try:
                shop = specialist.employee.shop
                service = Service.objects.get(id=service_id, shop=shop)
                attrs["service"] = service
            except Service.DoesNotExist:
                raise serializers.ValidationError(
                    {
                        "service_id": _(
                            "Service does not exist or doesn't belong to the shop."
                        )
                    }
                )
        elif service_id is not None:  # Explicitly set to null
            attrs["service"] = None

        # Validate category
        category_id = attrs.pop("category_id", None)
        if category_id:
            try:
                category = Category.objects.get(id=category_id)
                attrs["category"] = category
            except Category.DoesNotExist:
                raise serializers.ValidationError(
                    {"category_id": _("Category does not exist.")}
                )
        elif category_id is not None:  # Explicitly set to null
            attrs["category"] = None

        return attrs


# Create an alias for backward compatibility
SpecialistSerializer = SpecialistDetailSerializer
SpecialistMiniSerializer = SpecialistListSerializer
SpecialistBasicSerializer = SpecialistSerializer
