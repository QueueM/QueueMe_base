from rest_framework.views import APIView

from api.v1.throttling import PaymentRateThrottle, UserStrictRateThrottle


class ProcessPaymentView(APIView):
    """
    Process payment view
    """

    throttle_classes = [PaymentRateThrottle, UserStrictRateThrottle]

    # ... existing code ...


class RefundPaymentView(APIView):
    """
    Refund payment view
    """

    throttle_classes = [PaymentRateThrottle, UserStrictRateThrottle]

    # ... existing code ...


class PaymentMethodsView(APIView):
    """
    Payment methods view
    """

    throttle_classes = [PaymentRateThrottle]

    # ... existing code ...


class PaymentHistoryView(APIView):
    """
    Payment history view
    """

    throttle_classes = [PaymentRateThrottle]

    # ... existing code ...
