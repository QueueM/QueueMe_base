from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from .models import PaymentMethod, Refund, Transaction


class PaymentMethodSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = PaymentMethod
        fields = [
            "id",
            "type",
            "type_display",
            "last_digits",
            "expiry_month",
            "expiry_year",
            "card_brand",
            "is_default",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "last_digits",
            "expiry_month",
            "expiry_year",
            "card_brand",
            "created_at",
        ]


class AddPaymentMethodSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)
    payment_type = serializers.CharField(required=True)
    make_default = serializers.BooleanField(default=False)


class SetDefaultPaymentMethodSerializer(serializers.Serializer):
    payment_method_id = serializers.UUIDField(required=True)


class ContentTypeSerializer(serializers.Serializer):
    app_label = serializers.CharField()
    model = serializers.CharField()

    def validate(self, data):
        try:
            ContentType.objects.get(app_label=data["app_label"], model=data["model"])
            return data
        except ContentType.DoesNotExist:
            raise serializers.ValidationError(_("Invalid content type."))


class CreatePaymentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0.01)
    transaction_type = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True)
    payment_method_id = serializers.UUIDField(required=False, allow_null=True)
    payment_type = serializers.CharField(required=False)
    content_type = ContentTypeSerializer()
    object_id = serializers.UUIDField()

    def validate(self, data):
        # Ensure we have either payment_method_id or payment_type
        if not data.get("payment_method_id") and not data.get("payment_type"):
            raise serializers.ValidationError(
                _("Either payment_method_id or payment_type must be provided.")
            )

        # Check if content object exists
        try:
            content_type = ContentType.objects.get(
                app_label=data["content_type"]["app_label"],
                model=data["content_type"]["model"],
            )
            model_class = content_type.model_class()
            model_class.objects.get(id=data["object_id"])
        except (ContentType.DoesNotExist, Exception):
            raise serializers.ValidationError(_("The specified object does not exist."))

        return data


class TransactionSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    payment_method_details = PaymentMethodSerializer(
        source="payment_method", read_only=True
    )
    refund_count = serializers.SerializerMethodField()
    refunded_amount = serializers.SerializerMethodField()
    content_type_info = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        fields = [
            "id",
            "provider_transaction_id",  # external payment gateway ID
            "amount",
            "user",
            "currency",
            "status",
            "status_display",
            "wallet_type",
            "description",
            "content_type_info",
            "payment_method_details",
            "metadata",
            "created_at",
            "updated_at",
            "refund_count",
            "refunded_amount",
        ]
        read_only_fields = [
            "id",
            "provider_transaction_id",
            "status",
            "created_at",
            "updated_at",
        ]

    def get_refund_count(self, obj):
        return obj.refunds.count()

    def get_refunded_amount(self, obj):
        refunds = obj.refunds.filter(status="succeeded")
        if not refunds.exists():
            return 0
        return sum(refund.amount for refund in refunds)

    def get_content_type_info(self, obj):
        # Since your Transaction model does NOT have content_type, return None or blank info
        return None


class RefundSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    transaction_details = serializers.SerializerMethodField()

    class Meta:
        model = Refund
        fields = [
            "id",
            "provider_refund_id",  # external refund id (not 'moyasar_id')
            "transaction",
            "transaction_details",
            "amount",
            "reason",
            "status",
            "status_display",
            "created_at",
            "updated_at",
            "metadata",
        ]
        read_only_fields = [
            "id",
            "provider_refund_id",
            "status",
            "created_at",
            "updated_at",
        ]

    def get_transaction_details(self, obj):
        return {
            "id": str(obj.transaction.id),
            "provider_transaction_id": obj.transaction.provider_transaction_id,
            "amount": str(obj.transaction.amount),
            "status": obj.transaction.status,
        }


class CreateRefundSerializer(serializers.Serializer):
    transaction_id = serializers.UUIDField(required=True)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0.01)
    reason = serializers.CharField(required=True)

    def validate(self, data):
        try:
            transaction = Transaction.objects.get(id=data["transaction_id"])

            # Check if transaction can be refunded
            if transaction.status != "succeeded":
                raise serializers.ValidationError(
                    _("Only succeeded transactions can be refunded.")
                )

            # Check if refund amount is not greater than transaction amount
            total_refunded = sum(
                r.amount for r in transaction.refunds.filter(status="succeeded")
            )

            if data["amount"] > (transaction.amount - total_refunded):
                raise serializers.ValidationError(
                    _("Refund amount exceeds remaining transaction amount.")
                )

            data["transaction"] = transaction
            return data

        except Transaction.DoesNotExist:
            raise serializers.ValidationError(_("Transaction not found."))


class PaymentStatusSerializer(serializers.Serializer):
    transaction_id = serializers.UUIDField(required=True)
