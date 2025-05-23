"""
Authentication Serializers Module for QueueMe Backend

This module provides serializers for user authentication, registration, profile management,
and token handling. It ensures proper validation, data transformation, and security
for all authentication-related API operations.
"""

from typing import Any, Dict

from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.authapp.validators import normalize_phone_number

# Get the User model
User = get_user_model()


def validate_saudi_phone_number(phone_number: str) -> bool:
    """
    Validate Saudi phone number format.

    Args:
        phone_number: Normalized phone number string

    Returns:
        True if valid Saudi phone number, False otherwise
    """
    # Saudi phone numbers start with +966 and have 9 digits after country code
    if phone_number.startswith("+966"):
        number_part = phone_number[4:]  # Remove +966
        return len(number_part) == 9 and number_part.isdigit()
    return False


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for User model, used for profile management and user details.

    This serializer handles the representation of user data for API responses,
    with appropriate field-level permissions and validations.
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


class UserSimpleSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for User model, used for basic user information display.

    This serializer contains only essential user fields for display in feeds,
    comments, and other contexts where full user data is not needed.
    """

    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "first_name",
            "last_name",
            "full_name",
            "user_type",
        )
        read_only_fields = (
            "id",
            "first_name",
            "last_name",
            "full_name",
            "user_type",
        )

    def get_full_name(self, obj) -> str:
        """
        Get the user's full name.

        Args:
            obj: User instance

        Returns:
            Full name string
        """
        return obj.get_full_name()


class UserBasicSerializer(serializers.ModelSerializer):
    """
    Basic serializer for User model, used for minimal user information display.

    This serializer contains only the most essential user fields for display
    in reviews, ratings, and other contexts where minimal user data is needed.
    """

    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "first_name",
            "last_name",
            "full_name",
        )
        read_only_fields = (
            "id",
            "first_name",
            "last_name",
            "full_name",
        )

    def get_full_name(self, obj) -> str:
        """
        Get the user's full name.

        Args:
            obj: User instance

        Returns:
            Full name string
        """
        return obj.get_full_name()


class UserLightSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for User model, used for very minimal user information display.

    This serializer contains only the absolute essential user fields for display
    in roles, permissions, and other contexts where ultra-minimal user data is needed.
    """

    class Meta:
        model = User
        fields = (
            "id",
            "first_name",
            "last_name",
        )
        read_only_fields = (
            "id",
            "first_name",
            "last_name",
        )


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for updating user profile information.

    This serializer handles validation and updates for user profile data,
    ensuring proper formatting and data integrity.
    """

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "language_preference")

    def update(self, instance: User, validated_data: Dict[str, Any]) -> User:
        """
        Update user profile with validated data.

        Args:
            instance: User instance to update
            validated_data: Validated data dictionary

        Returns:
            Updated User instance
        """
        # Update user profile
        instance = super().update(instance, validated_data)

        # Mark profile as completed if all required fields are filled
        if instance.first_name and instance.last_name and instance.email:
            instance.profile_completed = True
            instance.save(update_fields=["profile_completed"])

        return instance


class PhoneNumberSerializer(serializers.Serializer):
    """
    Serializer for phone number validation and normalization.

    This serializer handles Saudi phone number validation and formatting
    for authentication and verification processes.
    """

    phone_number = serializers.CharField(max_length=20)

    def validate_phone_number(self, value: str) -> str:
        """
        Validate and normalize phone number.

        Args:
            value: Phone number string

        Returns:
            Normalized phone number

        Raises:
            serializers.ValidationError: If phone number is invalid
        """
        # Normalize the phone number
        normalized = normalize_phone_number(value)

        # Validate Saudi phone number format
        if not validate_saudi_phone_number(normalized):
            raise serializers.ValidationError(
                _("Please enter a valid Saudi phone number.")
            )

        return normalized


class OTPRequestSerializer(serializers.Serializer):
    """
    Serializer for OTP request.

    This serializer handles validation of OTP request for phone number verification,
    ensuring proper phone number format before sending OTP.
    """

    phone_number = serializers.CharField(max_length=20)

    def validate_phone_number(self, value: str) -> str:
        """
        Validate and normalize phone number.

        Args:
            value: Phone number string

        Returns:
            Normalized phone number

        Raises:
            serializers.ValidationError: If phone number is invalid
        """
        # Normalize the phone number
        normalized = normalize_phone_number(value)

        # Validate Saudi phone number format
        if not validate_saudi_phone_number(normalized):
            raise serializers.ValidationError(
                _("Please enter a valid Saudi phone number.")
            )

        return normalized


class OTPVerifySerializer(serializers.Serializer):
    """
    Serializer for OTP verification.

    This serializer handles validation of OTP verification requests,
    ensuring proper phone number and OTP code format for verification.
    """

    phone_number = serializers.CharField(max_length=20)
    code = serializers.CharField(max_length=6, min_length=4)

    def validate_phone_number(self, value: str) -> str:
        """
        Validate and normalize phone number.

        Args:
            value: Phone number string

        Returns:
            Normalized phone number

        Raises:
            serializers.ValidationError: If phone number is invalid
        """
        # Normalize the phone number
        normalized = normalize_phone_number(value)

        # Validate Saudi phone number format
        if not validate_saudi_phone_number(normalized):
            raise serializers.ValidationError(
                _("Please enter a valid Saudi phone number.")
            )

        return normalized

    def validate_code(self, value: str) -> str:
        """
        Validate OTP code format.

        Args:
            value: OTP code string

        Returns:
            Validated OTP code

        Raises:
            serializers.ValidationError: If code format is invalid
        """
        # Ensure code contains only digits
        if not value.isdigit():
            raise serializers.ValidationError(_("OTP code must contain only digits."))

        return value


class OTPVerificationSerializer(serializers.Serializer):
    """
    Serializer for OTP verification requests.

    This serializer handles validation of OTP verification requests,
    ensuring proper phone number and OTP code format.
    """

    phone_number = serializers.CharField(max_length=20)
    code = serializers.CharField(max_length=6, min_length=4)

    def validate_phone_number(self, value: str) -> str:
        """
        Validate and normalize phone number.

        Args:
            value: Phone number string

        Returns:
            Normalized phone number

        Raises:
            serializers.ValidationError: If phone number is invalid
        """
        # Normalize the phone number
        normalized = normalize_phone_number(value)

        # Validate Saudi phone number format
        if not validate_saudi_phone_number(normalized):
            raise serializers.ValidationError(
                _("Please enter a valid Saudi phone number.")
            )

        return normalized

    def validate_code(self, value: str) -> str:
        """
        Validate OTP code format.

        Args:
            value: OTP code string

        Returns:
            Validated OTP code

        Raises:
            serializers.ValidationError: If code format is invalid
        """
        # Ensure code contains only digits
        if not value.isdigit():
            raise serializers.ValidationError(_("OTP code must contain only digits."))

        return value


class TokenSerializer(serializers.Serializer):
    """
    Serializer for authentication tokens.

    This serializer handles the representation of authentication tokens
    for API responses, including access and refresh tokens.
    """

    access_token = serializers.CharField()
    refresh_token = serializers.CharField()
    token_type = serializers.CharField(default="Bearer")
    expires_in = serializers.IntegerField()
    user = UserSerializer(read_only=True)


class TokenRefreshSerializer(serializers.Serializer):
    """
    Serializer for token refresh requests.

    This serializer handles validation of token refresh requests,
    ensuring proper refresh token format.
    """

    refresh_token = serializers.CharField()

    def validate_refresh_token(self, value: str) -> str:
        """
        Validate refresh token format.

        Args:
            value: Refresh token string

        Returns:
            Validated refresh token

        Raises:
            serializers.ValidationError: If token format is invalid
        """
        # Basic format validation
        if len(value) < 10:
            raise serializers.ValidationError(_("Invalid refresh token format."))

        return value


class PasswordChangeSerializer(serializers.Serializer):
    """
    Serializer for password change requests.

    This serializer handles validation of password change requests,
    ensuring proper password format and security requirements.
    """

    current_password = serializers.CharField(style={"input_type": "password"})
    new_password = serializers.CharField(style={"input_type": "password"})

    def validate_new_password(self, value: str) -> str:
        """
        Validate new password meets security requirements.

        Args:
            value: New password string

        Returns:
            Validated new password

        Raises:
            serializers.ValidationError: If password doesn't meet requirements
        """
        # Check password length
        if len(value) < 8:
            raise serializers.ValidationError(
                _("Password must be at least 8 characters long.")
            )

        # Check password complexity
        has_digit = any(char.isdigit() for char in value)
        has_letter = any(char.isalpha() for char in value)

        if not (has_digit and has_letter):
            raise serializers.ValidationError(
                _("Password must contain both letters and numbers.")
            )

        return value


class UserDeviceSerializer(serializers.Serializer):
    """
    Serializer for user device registration.

    This serializer handles validation of device registration requests,
    ensuring proper device information for push notifications.
    """

    device_id = serializers.CharField()
    device_type = serializers.ChoiceField(choices=["ios", "android", "web"])
    push_token = serializers.CharField(required=False, allow_null=True)

    def validate_device_type(self, value: str) -> str:
        """
        Validate device type.

        Args:
            value: Device type string

        Returns:
            Validated device type

        Raises:
            serializers.ValidationError: If device type is invalid
        """
        # Convert to lowercase for consistency
        return value.lower()


class LoginSerializer(serializers.Serializer):
    """
    Serializer for user login requests.

    This serializer handles validation of login requests,
    supporting both phone number and email-based authentication.
    """

    phone_number = serializers.CharField(max_length=20, required=False)
    email = serializers.EmailField(required=False)
    password = serializers.CharField(style={"input_type": "password"}, required=False)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate login credentials.

        Args:
            attrs: Dictionary of field values

        Returns:
            Validated attributes

        Raises:
            serializers.ValidationError: If validation fails
        """
        phone_number = attrs.get("phone_number")
        email = attrs.get("email")
        attrs.get("password")

        # Ensure either phone number or email is provided
        if not phone_number and not email:
            raise serializers.ValidationError(
                _("Either phone number or email must be provided.")
            )

        # If phone number is provided, validate it
        if phone_number:
            normalized = normalize_phone_number(phone_number)
            if not validate_saudi_phone_number(normalized):
                raise serializers.ValidationError(
                    _("Please enter a valid Saudi phone number.")
                )
            attrs["phone_number"] = normalized

        return attrs

    def validate_phone_number(self, value: str) -> str:
        """
        Validate and normalize phone number.

        Args:
            value: Phone number string

        Returns:
            Normalized phone number
        """
        if value:
            return normalize_phone_number(value)
        return value


class ChangeLanguageSerializer(serializers.Serializer):
    """
    Serializer for changing user language preference.

    This serializer handles validation of language change requests,
    ensuring the language code is valid and supported.
    """

    language_preference = serializers.CharField(max_length=10)

    def validate_language_preference(self, value: str) -> str:
        """
        Validate language preference code.

        Args:
            value: Language code string

        Returns:
            Validated language code

        Raises:
            serializers.ValidationError: If language code is invalid
        """
        # Define supported languages (adjust based on your requirements)
        SUPPORTED_LANGUAGES = ["en", "ar", "en-us", "ar-sa"]

        # Convert to lowercase for consistency
        value = value.lower()

        # Check if language is supported
        if value not in SUPPORTED_LANGUAGES:
            raise serializers.ValidationError(
                _("Language '{}' is not supported. Supported languages: {}").format(
                    value, ", ".join(SUPPORTED_LANGUAGES)
                )
            )

        return value
