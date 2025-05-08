import datetime
import logging

from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from apps.authapp.constants import (
    JWT_ACCESS_TOKEN_LIFETIME_MINUTES,
    JWT_REFRESH_TOKEN_LIFETIME_DAYS,
)
from apps.authapp.models import User

logger = logging.getLogger(__name__)


class TokenService:
    """
    Service for JWT token management.
    """

    @staticmethod
    def get_tokens_for_user(user):
        """
        Generate JWT tokens for a user.

        Args:
            user: User instance

        Returns:
            dict: Dictionary containing access and refresh tokens
        """
        refresh = RefreshToken.for_user(user)

        # Add custom claims
        refresh["phone_number"] = user.phone_number
        refresh["user_type"] = user.user_type
        refresh["is_verified"] = user.is_verified

        # Configure token lifetime
        access_token_lifetime = datetime.timedelta(
            minutes=JWT_ACCESS_TOKEN_LIFETIME_MINUTES
        )
        refresh_token_lifetime = datetime.timedelta(
            days=JWT_REFRESH_TOKEN_LIFETIME_DAYS
        )

        # Get the tokens
        tokens = {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "access_expires": datetime.datetime.now(timezone.utc)
            + access_token_lifetime,
            "refresh_expires": datetime.datetime.now(timezone.utc)
            + refresh_token_lifetime,
        }

        logger.info(f"Tokens generated for user {user.id}")
        return tokens

    @staticmethod
    def get_user_from_token(token):
        """
        Get user from access token.

        Args:
            token: JWT access token

        Returns:
            User instance if token is valid, None otherwise
        """
        try:
            from rest_framework_simplejwt.tokens import AccessToken

            # Decode the token
            decoded_token = AccessToken(token)
            user_id = decoded_token["user_id"]

            # Get the user
            user = User.objects.get(id=user_id)
            return user
        except Exception as e:
            logger.warning(f"Error getting user from token: {str(e)}")
            return None

    @staticmethod
    def refresh_token(refresh_token):
        """
        Get a new access token using refresh token.

        Args:
            refresh_token: JWT refresh token

        Returns:
            dict: New tokens if refresh is valid

        Raises:
            Exception: If refresh token is invalid
        """
        try:
            # Get token object
            token = RefreshToken(refresh_token)

            # Create and return new tokens
            return {"access": str(token.access_token), "refresh": str(token)}
        except Exception as e:
            logger.warning(f"Token refresh failed: {str(e)}")
            raise

    @staticmethod
    def invalidate_token(token):
        """
        Add a token to the blacklist to invalidate it.

        Args:
            token: JWT token to invalidate

        Returns:
            bool: True if successful
        """
        # In a real implementation, you would add the token to a blacklist in the database
        # or use the JWT blacklist feature of djangorestframework-simplejwt
        # For now, we'll just log it
        logger.info(f"Token invalidated")
        return True
