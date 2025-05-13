from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.authapp.validators import normalize_phone_number

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for User model, used for profile management.
    """

    class Meta:
        model = User
        fields = (
            "id",
            "phone_number",
            "email",
            "first_name",
            "last_name",
            "user_type",
            "is_verified",
            "profile_completed",
            "language_preference",
            "date_joined",
        )
        read_only_fields = (
            "id",
            "phone_number",
            "is_verified",
            "date_joined",
            "user_type",
        )


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for updating user profile information.
    """

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "language_preference")

    def update(self, instance, validated_data):
        # Update user profile
        instance = super().update(instance, validated_data)

        # Check if profile is now complete
        if instance.first_name and instance.last_name:
            instance.profile_completed = True
            instance.save(update_fields=["profile_completed"])

        return instance


class OTPRequestSerializer(serializers.Serializer):
    """
    Serializer for OTP request endpoint.
    """

    phone_number = serializers.CharField(max_length=20)

    def validate_phone_number(self, value):
        """
        Validate and normalize the phone number.
        """
        try:
            return normalize_phone_number(value)
        except Exception:
            raise serializers.ValidationError(_("Enter a valid phone number."))


class OTPVerifySerializer(serializers.Serializer):
    """
    Serializer for OTP verification endpoint.
    """

    phone_number = serializers.CharField(max_length=20)
    code = serializers.CharField(max_length=10)

    def validate_phone_number(self, value):
        """
        Validate and normalize the phone number.
        """
        try:
            return normalize_phone_number(value)
        except Exception:
            raise serializers.ValidationError(_("Enter a valid phone number."))


class LoginSerializer(serializers.Serializer):
    """
    Serializer for standard login endpoint (alternative to OTP).
    """

    phone_number = serializers.CharField(max_length=20)
    password = serializers.CharField(max_length=128, write_only=True)

    def validate_phone_number(self, value):
        """
        Validate and normalize the phone number.
        """
        try:
            return normalize_phone_number(value)
        except Exception:
            raise serializers.ValidationError(_("Enter a valid phone number."))


class TokenRefreshSerializer(serializers.Serializer):
    """
    Serializer for token refresh endpoint.
    """

    refresh = serializers.CharField()


class ChangeLanguageSerializer(serializers.Serializer):
    """
    Serializer for changing language preference.
    """

    language = serializers.ChoiceField(choices=[("en", "English"), ("ar", "Arabic")])


class UserLightSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for User model, used for basic user information.
    """

    class Meta:
        model = User
        fields = (
            "id",
            "phone_number",
            "email",
            "first_name",
            "last_name",
            "user_type",
        )
        read_only_fields = fields


UserSimpleSerializer = UserSerializer
UserBasicSerializer = UserSimpleSerializer
