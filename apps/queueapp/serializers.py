from rest_framework import serializers

from apps.authapp.serializers import UserSerializer
from apps.serviceapp.serializers import ServiceSerializer
from apps.shopapp.serializers import ShopSerializer
from apps.specialistsapp.serializers import SpecialistSerializer

from .models import Queue, QueueTicket


class QueueSerializer(serializers.ModelSerializer):
    shop_details = ShopSerializer(source="shop", read_only=True)
    active_tickets_count = serializers.SerializerMethodField()
    waiting_tickets_count = serializers.SerializerMethodField()

    class Meta:
        model = Queue
        fields = [
            "id",
            "shop",
            "shop_details",
            "name",
            "status",
            "max_capacity",
            "created_at",
            "updated_at",
            "active_tickets_count",
            "waiting_tickets_count",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_active_tickets_count(self, obj):
        return QueueTicket.objects.filter(
            queue=obj, status__in=["waiting", "called", "serving"]
        ).count()

    def get_waiting_tickets_count(self, obj):
        return QueueTicket.objects.filter(queue=obj, status="waiting").count()


class QueueTicketSerializer(serializers.ModelSerializer):
    queue_details = QueueSerializer(source="queue", read_only=True)
    customer_details = UserSerializer(source="customer", read_only=True)
    service_details = ServiceSerializer(source="service", read_only=True)
    specialist_details = SpecialistSerializer(source="specialist", read_only=True)

    class Meta:
        model = QueueTicket
        fields = [
            "id",
            "queue",
            "queue_details",
            "ticket_number",
            "customer",
            "customer_details",
            "service",
            "service_details",
            "specialist",
            "specialist_details",
            "status",
            "position",
            "estimated_wait_time",
            "actual_wait_time",
            "notes",
            "join_time",
            "called_time",
            "serve_time",
            "complete_time",
        ]
        read_only_fields = [
            "id",
            "ticket_number",
            "position",
            "estimated_wait_time",
            "actual_wait_time",
            "join_time",
            "called_time",
            "serve_time",
            "complete_time",
        ]


class QueueJoinSerializer(serializers.Serializer):
    queue_id = serializers.UUIDField(required=True)
    customer_id = serializers.UUIDField(required=True)
    service_id = serializers.UUIDField(required=False, allow_null=True)


class QueueCallNextSerializer(serializers.Serializer):
    queue_id = serializers.UUIDField(required=True)
    specialist_id = serializers.UUIDField(required=False, allow_null=True)


class TicketUpdateSerializer(serializers.Serializer):
    ticket_id = serializers.UUIDField(required=True)
    specialist_id = serializers.UUIDField(required=False, allow_null=True)


class QueueTicketPositionSerializer(serializers.Serializer):
    ticket_number = serializers.CharField(required=True)
    queue_id = serializers.UUIDField(required=True)
