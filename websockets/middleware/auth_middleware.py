"""
Authentication middleware for WebSocket connections.

This middleware authenticates WebSocket connections using JWT tokens.
"""

import logging
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware

from apps.authapp.services.token_service import TokenService

logger = logging.getLogger(__name__)


class JWTAuthMiddleware(BaseMiddleware):
    """
    JWT authentication middleware for WebSocket connections.

    This middleware extracts and validates JWT tokens from the WebSocket query string.
    If valid, it sets the authenticated user on the connection scope.
    """

    async def __call__(self, scope, receive, send):
        """Process the WebSocket connection."""
        try:
            # Extract token from query string
            query_string = parse_qs(scope.get("query_string", b"").decode())
            token = query_string.get("token", [None])[0]

            if not token:
                logger.warning("WebSocket connection rejected: No token provided")
                await self.close_connection(scope, receive, send, 4001)
                return

            # Verify token and get user
            user = await database_sync_to_async(TokenService.get_user_from_token)(token)

            if not user:
                logger.warning("WebSocket connection rejected: Invalid token")
                await self.close_connection(scope, receive, send, 4001)
                return

            if not user.is_active:
                logger.warning(f"WebSocket connection rejected: User {user.id} is inactive")
                await self.close_connection(scope, receive, send, 4002)
                return

            # Set authenticated user on scope
            scope["user"] = user
            scope["user_id"] = str(user.id)
            scope["auth_token"] = token

            logger.info(f"WebSocket connection authenticated for user {user.id}")
            return await super().__call__(scope, receive, send)

        except Exception as e:
            logger.error(f"Error in WebSocket authentication: {str(e)}")
            await self.close_connection(scope, receive, send, 4000)
            return

    async def close_connection(self, scope, receive, send, code):
        """Close the WebSocket connection with a specific code."""
        try:
            await send({"type": "websocket.close", "code": code})
        except Exception as e:
            logger.error(f"Error closing WebSocket connection: {str(e)}")


def JWTAuthMiddlewareStack(inner):
    """Helper function to include JWTAuthMiddleware in the middleware stack."""
    return JWTAuthMiddleware(inner)
