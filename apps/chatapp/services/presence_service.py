import logging

from django.db import transaction
from django.utils import timezone

from apps.authapp.models import User
from apps.chatapp.models import Presence, TypingStatus

logger = logging.getLogger("chatapp.services")


class PresenceService:
    """Service for managing user presence and typing status"""

    @staticmethod
    @transaction.atomic
    def set_user_online(user_id, conversation_id):
        """Mark user as online in a conversation"""
        user = User.objects.get(id=user_id)

        # Get or create presence record
        presence, created = Presence.objects.get_or_create(
            user=user,
            conversation_id=conversation_id,
            defaults={"is_online": True, "last_seen": timezone.now()},
        )

        # If not created, update
        if not created:
            presence.is_online = True
            presence.last_seen = timezone.now()
            presence.save()

        return presence

    @staticmethod
    @transaction.atomic
    def set_user_offline(user_id, conversation_id):
        """Mark user as offline in a conversation"""
        user = User.objects.get(id=user_id)

        try:
            # Get presence record
            presence = Presence.objects.get(user=user, conversation_id=conversation_id)

            # Update status
            presence.is_online = False
            presence.last_seen = timezone.now()
            presence.save()

            # Also reset typing status
            PresenceService.set_typing_status(user_id, conversation_id, False)

            return presence
        except Presence.DoesNotExist:
            logger.warning(
                f"Presence record not found for user {user_id} in conversation {conversation_id}"
            )
            return None

    @staticmethod
    @transaction.atomic
    def set_typing_status(user_id, conversation_id, is_typing):
        """Update typing status for a user"""
        user = User.objects.get(id=user_id)

        # Get or create typing status record
        typing_status, created = TypingStatus.objects.get_or_create(
            user=user,
            conversation_id=conversation_id,
            defaults={"is_typing": is_typing},
        )

        # If not created, update
        if not created and typing_status.is_typing != is_typing:
            typing_status.is_typing = is_typing
            typing_status.save()

        return typing_status

    @staticmethod
    def get_conversation_presence(conversation_id):
        """Get presence status for all users in a conversation"""
        # Get all presence records for the conversation
        presence_records = Presence.objects.filter(conversation_id=conversation_id)

        # Build presence map
        presence_map = {}
        for record in presence_records:
            presence_map[str(record.user.id)] = {
                "is_online": record.is_online,
                "last_seen": record.last_seen,
            }

        return presence_map

    @staticmethod
    def get_conversation_typing_status(conversation_id):
        """Get typing status for all users in a conversation"""
        # Get all typing status records for the conversation
        typing_records = TypingStatus.objects.filter(
            conversation_id=conversation_id, is_typing=True  # Only get active typing
        )

        # Build typing map
        typing_map = {}
        for record in typing_records:
            typing_map[str(record.user.id)] = {
                "is_typing": record.is_typing,
                "updated_at": record.updated_at,
            }

        return typing_map

    @staticmethod
    def cleanup_stale_presence(idle_minutes=30):
        """Mark idle users as offline"""
        idle_threshold = timezone.now() - timezone.timedelta(minutes=idle_minutes)

        # Find stale online records
        stale_records = Presence.objects.filter(is_online=True, last_seen__lt=idle_threshold)

        # Update records
        count = stale_records.count()
        stale_records.update(is_online=False)

        return count
