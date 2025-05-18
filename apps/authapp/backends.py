from django.contrib.auth.backends import ModelBackend
from django.db.models import Q
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed, InvalidToken


class PhoneNumberBackend(ModelBackend):
    def authenticate(self, request, phone_number=None, password=None, **kwargs):
        from apps.authapp.models import User

        if phone_number is None:
            phone_number = kwargs.get("username")

        if phone_number is None or password is None:
            return None

        try:
            # Clean phone number format if needed
            if phone_number.startswith("+"):
                phone_number = phone_number[1:]
            elif phone_number.startswith("0"):
                phone_number = "966" + phone_number[1:]

            user = User.objects.get(
                Q(phone_number=phone_number)
                | Q(phone_number="966" + phone_number)
                | Q(phone_number="+" + phone_number)
                | Q(phone_number="+966" + phone_number)
            )

            if user.check_password(password):
                return user

        except User.DoesNotExist:
            # Run the default password hasher once to reduce timing
            # attack vector (see comments for more details)
            User().set_password(password)

        return None


class QueueMeJWTAuthentication(JWTAuthentication):
    """
    Custom JWT authentication that properly validates if a user is active.

    This addresses CVE-2024-22513 in djangorestframework-simplejwt where
    disabled user accounts could still access resources.
    """

    def get_user(self, validated_token):
        """
        Attempt to find and return a user using the given validated token.
        Adds explicit check for user.is_active.
        """
        try:
            user = super().get_user(validated_token)

            # The critical fix: explicitly check if user is active
            if not user.is_active:
                raise AuthenticationFailed("User account is disabled")

            return user

        except AuthenticationFailed:
            raise
        except Exception as e:
            raise InvalidToken(f"Token contained invalid user identification: {e}")
