import json

from django.core.cache import cache

from ..models import SystemSetting


class SettingsService:
    """
    Service for managing system settings with caching.
    """

    CACHE_KEY_PREFIX = "system_setting_"
    CACHE_TIMEOUT = 3600  # 1 hour

    @staticmethod
    def get_setting(key, default=None, use_cache=True):
        """
        Get a system setting value with caching.

        Args:
            key: Setting key
            default: Default value if not found
            use_cache: Whether to use cache (default: True)

        Returns:
            The setting value or default
        """
        key = key.upper()  # Standardize to uppercase
        cache_key = SettingsService.CACHE_KEY_PREFIX + key

        # Try cache first if enabled
        if use_cache:
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value

        # Not in cache or cache disabled, get from database
        try:
            setting = SystemSetting.objects.get(key=key)
            value = setting.value

            # Try to parse JSON values if possible
            try:
                value = json.loads(value)
            except (ValueError, TypeError):
                # Not JSON, use as is
                pass

            # Cache the value
            if use_cache:
                cache.set(cache_key, value, SettingsService.CACHE_TIMEOUT)

            return value
        except SystemSetting.DoesNotExist:
            return default

    @staticmethod
    def set_setting(key, value, category=None, description=None, is_public=None):
        """
        Update or create a system setting with cache invalidation.

        Args:
            key: Setting key
            value: Setting value
            category: Setting category (optional)
            description: Setting description (optional)
            is_public: Whether the setting is public (optional)

        Returns:
            SystemSetting: The updated or created setting
        """
        key = key.upper()  # Standardize to uppercase
        cache_key = SettingsService.CACHE_KEY_PREFIX + key

        # Convert non-string values to JSON
        if not isinstance(value, str):
            value = json.dumps(value)

        # Create or update setting
        setting, created = SystemSetting.objects.update_or_create(
            key=key,
            defaults={
                "value": value,
                "category": category if category is not None else "general",
                "description": description if description is not None else "",
                "is_public": is_public if is_public is not None else False,
            },
        )

        # Invalidate cache
        cache.delete(cache_key)

        return setting

    @staticmethod
    def delete_setting(key):
        """
        Delete a system setting with cache invalidation.

        Args:
            key: Setting key

        Returns:
            bool: Whether a setting was deleted
        """
        key = key.upper()  # Standardize to uppercase
        cache_key = SettingsService.CACHE_KEY_PREFIX + key

        # Delete from database
        count, _ = SystemSetting.objects.filter(key=key).delete()

        # Invalidate cache
        cache.delete(cache_key)

        return count > 0

    @staticmethod
    def get_all_settings(category=None, public_only=False):
        """
        Get all system settings, optionally filtered.

        Args:
            category: Filter by category (optional)
            public_only: Only return public settings (default: False)

        Returns:
            dict: Dictionary of settings {key: value}
        """
        # Build query
        query = SystemSetting.objects.all()

        if category:
            query = query.filter(category=category)

        if public_only:
            query = query.filter(is_public=True)

        # Convert to dictionary
        settings_dict = {}
        for setting in query:
            # Try to parse JSON values
            try:
                value = json.loads(setting.value)
            except (ValueError, TypeError):
                value = setting.value

            settings_dict[setting.key] = value

        return settings_dict

    @staticmethod
    def clear_settings_cache():
        """
        Clear all settings cache.

        Returns:
            bool: Always True
        """
        # Get all setting keys
        keys = SystemSetting.objects.values_list("key", flat=True)

        # Delete each setting cache
        for key in keys:
            cache_key = SettingsService.CACHE_KEY_PREFIX + key
            cache.delete(cache_key)

        return True
