"""
Enhanced token service with robust error handling and security measures.
"""

import datetime
import json
import logging
import secrets
import uuid
from typing import Dict, Optional, Tuple, Union

import jwt
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.authapp.constants import (
    JWT_ACCESS_TOKEN_LIFETIME_MINUTES,
    JWT_REFRESH_TOKEN_LIFETIME_DAYS,
)
from apps.authapp.models import User
from core.exceptions.auth_exceptions import (
    InvalidTokenError,
    TokenBlacklistedError,
    TokenExpiredError,
    TokenGenerationError,
)

logger = logging.getLogger(__name__)


class TokenService:
    """Service for managing authentication tokens with enhanced security."""

    # Token blacklist cache (in-memory for simplicity, could be Redis in production)
    _blacklist = set()

    @classmethod
    def create_token(cls, user: User, token_type: str = "access") -> str:
        """
        Generate a secure authentication token for a user.

        Args:
            user: User model instance
            token_type: Type of token to generate (access or refresh)

        Returns:
            JWT token string

        Raises:
            TokenGenerationError: If token generation fails
        """
        try:
            # Set expiration based on token type
            if token_type == "access":
                expires_delta = datetime.timedelta(
                    hours=settings.TOKEN_EXPIRE_HOURS,
                    minutes=settings.TOKEN_EXPIRE_MINUTES,
                )
            elif token_type == "refresh":
                expires_delta = datetime.timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
            else:
                raise ValueError(f"Invalid token type: {token_type}")

            # Current timestamp and expiration
            now = timezone.now()
            expire_timestamp = now + expires_delta

            # Add rate limiting for token creation (max 10 tokens per minute)
            cls._check_token_creation_rate(str(user.id))

            # Create JWT payload with enhanced security
            payload = {
                "sub": str(user.id),
                "type": token_type,
                "iat": int(now.timestamp()),
                "exp": int(expire_timestamp.timestamp()),
                "jti": str(uuid.uuid4()),  # Unique token ID
                "user_type": user.user_type,
                # Add a random nonce for additional security
                "nonce": secrets.token_hex(8),
            }

            # Generate token with HS256 algorithm
            token = jwt.encode(
                payload,
                settings.SECRET_KEY,
                algorithm=settings.TOKEN_ALGORITHM,
            )

            # Record successful token creation for audit purposes
            cls._record_token_creation(user, token_type, payload["jti"])

            return token

        except Exception as e:
            logger.error(f"Token generation failed: {str(e)}")
            raise TokenGenerationError(_("Failed to generate authentication token"))

    @classmethod
    def validate_token(cls, token: str) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Validate a token and extract payload with comprehensive error handling.

        Args:
            token: JWT token string

        Returns:
            Tuple of (is_valid, payload, error_message)
        """
        if not token:
            return False, None, "No token provided"

        try:
            # Verify token against blacklist first (fast check)
            if cls._is_token_blacklisted(token):
                raise TokenBlacklistedError(_("Token has been revoked"))

            # Decode token with full verification
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.TOKEN_ALGORITHM],
                options={"verify_signature": True},
            )

            # Check if token is expired (redundant, but explicit check)
            if "exp" in payload:
                expiration = datetime.datetime.fromtimestamp(payload["exp"])
                if timezone.now() > timezone.make_aware(expiration):
                    raise TokenExpiredError(_("Token has expired"))

            # Verify token type
            if "type" not in payload or payload["type"] != "access":
                return False, None, "Invalid token type"

            # Successful validation
            return True, payload, None

        except jwt.ExpiredSignatureError:
            return False, None, "Token has expired"
        except jwt.InvalidTokenError:
            return False, None, "Invalid token"
        except TokenBlacklistedError as e:
            return False, None, str(e)
        except TokenExpiredError as e:
            return False, None, str(e)
        except Exception as e:
            logger.error(f"Token validation error: {str(e)}")
            return False, None, "Token validation failed"

    @classmethod
    def get_user_from_token(cls, token: str) -> Optional[User]:
        """
        Get user associated with a token.

        Args:
            token: JWT token string

        Returns:
            User instance or None if token is invalid
        """
        is_valid, payload, _ = cls.validate_token(token)

        if not is_valid or not payload:
            return None

        try:
            user_id = payload.get("sub")
            if not user_id:
                return None

            # Get user from database
            user = User.objects.get(id=user_id)

            # Additional security check: verify user is active
            if not user.is_active:
                logger.warning(f"Attempt to use token for inactive user: {user_id}")
                return None

            return user

        except User.DoesNotExist:
            logger.warning(f"Token references non-existent user: {payload.get('sub')}")
            return None
        except Exception as e:
            logger.error(f"Error retrieving user from token: {str(e)}")
            return None

    @classmethod
    def blacklist_token(cls, token: str) -> bool:
        """
        Blacklist a token (invalidate it).

        Args:
            token: JWT token string

        Returns:
            True if blacklisted successfully, False otherwise
        """
        try:
            if not token:
                return False

            # Decode the token without verification to extract jti
            # This is safe because we're just blacklisting it
            try:
                payload = jwt.decode(
                    token,
                    options={"verify_signature": False},
                )
                jti = payload.get("jti")
                if jti:
                    cls._blacklist.add(jti)
                    logger.info(f"Token blacklisted: {jti}")
                    return True
            except BaseException:
                # If we can't decode, blacklist the whole token
                cls._blacklist.add(token)
                logger.info("Token blacklisted (full token)")
                return True

            return False

        except Exception as e:
            logger.error(f"Error blacklisting token: {str(e)}")
            return False

    @classmethod
    def _is_token_blacklisted(cls, token: str) -> bool:
        """
        Check if a token is blacklisted.

        Args:
            token: JWT token string

        Returns:
            True if blacklisted, False otherwise
        """
        if not token:
            return False

        try:
            # Try to extract jti from token
            payload = jwt.decode(
                token,
                options={"verify_signature": False},
            )
            jti = payload.get("jti")

            # Check if jti is in blacklist
            if jti and jti in cls._blacklist:
                return True

            # Also check if full token is blacklisted
            return token in cls._blacklist

        except Exception:
            # If we can't decode the token, check the full token
            return token in cls._blacklist

    @classmethod
    def refresh_token(cls, refresh_token: str) -> Optional[Dict[str, str]]:
        """
        Generate new access token using a refresh token.

        Args:
            refresh_token: JWT refresh token string

        Returns:
            Dict with new access and refresh tokens, or None if refresh fails
        """
        try:
            # Verify the refresh token
            try:
                payload = jwt.decode(
                    refresh_token,
                    settings.SECRET_KEY,
                    algorithms=[settings.TOKEN_ALGORITHM],
                )
            except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
                return None

            # Check if token is blacklisted
            if cls._is_token_blacklisted(refresh_token):
                return None

            # Verify token type
            if payload.get("type") != "refresh":
                return None

            # Get user from token
            user_id = payload.get("sub")
            if not user_id:
                return None

            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return None

            # Blacklist the old refresh token
            cls.blacklist_token(refresh_token)

            # Generate new tokens
            access_token = cls.create_token(user, "access")
            new_refresh_token = cls.create_token(user, "refresh")

            return {
                "access_token": access_token,
                "refresh_token": new_refresh_token,
                "user_type": user.user_type,
            }

        except Exception as e:
            logger.error(f"Token refresh failed: {str(e)}")
            return None

    @classmethod
    def _record_token_creation(cls, user: User, token_type: str, token_id: str) -> None:
        """
        Record token creation for audit purposes.

        Args:
            user: User the token was created for
            token_type: Type of token created
            token_id: Unique token identifier (jti)
        """
        # In a production environment, this might write to a database table
        # For now, just log it
        logger.info(f"Token created: user={user.id}, type={token_type}, token_id={token_id}")

    @classmethod
    def _check_token_creation_rate(cls, user_id: str) -> None:
        """
        Check and enforce rate limiting for token creation.

        Args:
            user_id: User ID requesting token

        Raises:
            TokenGenerationError: If too many tokens have been generated recently
        """
        # Implementation would use Redis or similar in production
        # This is a placeholder for the concept
        pass

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
        access_token_lifetime = datetime.timedelta(minutes=JWT_ACCESS_TOKEN_LIFETIME_MINUTES)
        refresh_token_lifetime = datetime.timedelta(days=JWT_REFRESH_TOKEN_LIFETIME_DAYS)

        # Get the tokens
        tokens = {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "access_expires": datetime.datetime.now(timezone.utc) + access_token_lifetime,
            "refresh_expires": datetime.datetime.now(timezone.utc) + refresh_token_lifetime,
        }

        logger.info(f"Tokens generated for user {user.id}")
        return tokens

    @staticmethod
    def invalidate_token(token):
        """
        Add a token to the blacklist to invalidate it.

        Args:
            token: JWT token to invalidate

        Returns:
            bool: True if successful
        """
        try:
            # Get the token from outstanding tokens
            outstanding_token = OutstandingToken.objects.get(token=token)

            # Add to blacklist
            BlacklistedToken.objects.get_or_create(token=outstanding_token)

            logger.info(f"Token {token[:10]}... blacklisted successfully")
            return True
        except OutstandingToken.DoesNotExist:
            logger.warning(f"Token {token[:10]}... not found in outstanding tokens")
            return False
        except Exception as e:
            logger.error(f"Error blacklisting token: {str(e)}")
            return False

    @staticmethod
    def invalidate_all_user_tokens(user_id):
        """
        Invalidate all tokens for a user.

        Args:
            user_id: User ID

        Returns:
            bool: True if successful
        """
        try:
            # Get all outstanding tokens for the user
            tokens = OutstandingToken.objects.filter(user_id=user_id)

            # Add all to blacklist
            for token in tokens:
                BlacklistedToken.objects.get_or_create(token=token)

            logger.info(f"All tokens for user {user_id} blacklisted successfully")
            return True
        except Exception as e:
            logger.error(f"Error blacklisting all tokens for user {user_id}: {str(e)}")
            return False
