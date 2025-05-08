"""
Authentication middleware for WebSocket connections.

This middleware authenticates WebSocket connections using JWT tokens.
"""

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware

from apps.authapp.services.token_service import TokenService


class JWTAuthMiddleware(BaseMiddleware):
    """
    JWT authentication middleware for WebSocket connections.

    This middleware extracts and validates JWT tokens from the WebSocket query string.
    If valid, it sets the authenticated user on the connection scope.
    """

    async def __call__(self, scope, receive, send):
        """Process the WebSocket connection."""
        # Extract token from query string
        query_string = parse_qs(scope.get("query_string", b"").decode())
        token = query_string.get("token", [None])[0]

        if token:
            # Verify token and get user
            user = await database_sync_to_async(TokenService.get_user_from_token)(token)

            if user:
                # Set authenticated user on scope
                scope["user"] = user
                scope["user_id"] = str(user.id)

        return await super().__call__(scope, receive, send)


def JWTAuthMiddlewareStack(inner):
    """Helper function to include JWTAuthMiddleware in the middleware stack."""
    return JWTAuthMiddleware(inner)
