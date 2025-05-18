"""
Rate limiting middleware for WebSocket connections.

This middleware limits the rate of WebSocket connections and messages
to prevent abuse and ensure fair resource allocation.
"""

import time
from collections import defaultdict, deque

from channels.middleware import BaseMiddleware

# Module-level constants for rate limits
MAX_CONNECTIONS_PER_MINUTE = 10  # Max connections per minute per client
MAX_MESSAGES_PER_MINUTE = 60  # Max messages per minute per client


class WebsocketRateLimiter(BaseMiddleware):
    """
    Rate limiting middleware for WebSocket connections.

    This middleware implements two types of rate limiting:
    1. Connection rate limiting: Limits how often a client can connect
    2. Message rate limiting: Limits how many messages a client can send in a time period
    """

    # Storage for rate tracking
    # Use the module-level constants for maxlen
    connection_history = defaultdict(lambda: deque(maxlen=MAX_CONNECTIONS_PER_MINUTE))
    message_history = defaultdict(lambda: deque(maxlen=MAX_MESSAGES_PER_MINUTE))

    async def __call__(self, scope, receive, send):
        """Process the WebSocket connection."""
        # Get client identifier (IP address or user ID if authenticated)
        client_id = self.get_client_id(scope)

        # Apply connection rate limiting (only for connect event)
        if scope["type"] == "websocket" and scope.get("path", "").startswith("/ws/"):
            # Check connection rate
            if not self.check_connection_rate(client_id):
                # Too many connection attempts, close with rate limit error
                await send(
                    {
                        "type": "websocket.close",
                        "code": 4429,  # Custom code for rate limiting
                    }
                )
                return

        # Wrap receive function to apply message rate limiting
        original_receive = receive

        async def rate_limited_receive():
            message = await original_receive()

            # Apply message rate limiting (only for websocket.receive)
            if message["type"] == "websocket.receive":
                if not self.check_message_rate(client_id):
                    # Too many messages, close with rate limit error
                    await send(
                        {
                            "type": "websocket.close",
                            "code": 4429,
                        }
                    )
                    return {"type": "websocket.close"}

            return message

        # Continue with modified receive function
        return await super().__call__(scope, rate_limited_receive, send)

    def get_client_id(self, scope):
        """Get a unique identifier for the client."""
        # Use user ID if authenticated
        if "user_id" in scope:
            return f"user:{scope['user_id']}"

        # Fall back to client IP
        client = scope.get("client", ["0.0.0.0", 0])
        return f"ip:{client[0]}"

    def check_connection_rate(self, client_id):
        """Check if client is within connection rate limits."""
        now = time.time()
        history = self.connection_history[client_id]

        # If queue is full, check the oldest timestamp
        if len(history) == self.MAX_CONNECTIONS_PER_MINUTE:
            # If oldest timestamp is less than 60 seconds ago, rate limit exceeded
            if now - history[0] < 60:
                return False

        # Add current timestamp to history
        history.append(now)
        return True

    def check_message_rate(self, client_id):
        """Check if client is within message rate limits."""
        now = time.time()
        history = self.message_history[client_id]

        # If queue is full, check the oldest timestamp
        if len(history) == self.MAX_MESSAGES_PER_MINUTE:
            # If oldest timestamp is less than 60 seconds ago, rate limit exceeded
            if now - history[0] < 60:
                return False

        # Add current timestamp to history
        history.append(now)
        return True


def WebsocketRateLimiterStack(inner):
    """Helper function to include WebsocketRateLimiter in the middleware stack."""
    return WebsocketRateLimiter(inner)
