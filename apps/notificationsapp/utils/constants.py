"""
Notification constants used throughout the application.
"""

# Notification types
NOTIFICATION_TYPES = {
    "APPOINTMENT_CONFIRMATION": "appointment_confirmation",
    "APPOINTMENT_REMINDER": "appointment_reminder",
    "APPOINTMENT_CANCELLATION": "appointment_cancellation",
    "APPOINTMENT_RESCHEDULE": "appointment_reschedule",
    "QUEUE_JOIN_CONFIRMATION": "queue_join_confirmation",
    "QUEUE_STATUS_UPDATE": "queue_status_update",
    "QUEUE_CALLED": "queue_called",
    "QUEUE_CANCELLED": "queue_cancelled",
    "NEW_MESSAGE": "new_message",
    "PAYMENT_CONFIRMATION": "payment_confirmation",
    "SERVICE_FEEDBACK": "service_feedback",
    "VERIFICATION_CODE": "verification_code",
    "WELCOME": "welcome",
    "PASSWORD_RESET": "password_reset",
}

# Notification channels
NOTIFICATION_CHANNELS = {
    "SMS": "sms",
    "PUSH": "push",
    "EMAIL": "email",
    "IN_APP": "in_app",
}

# Notification statuses
NOTIFICATION_STATUSES = {
    "PENDING": "pending",
    "SENT": "sent",
    "DELIVERED": "delivered",
    "FAILED": "failed",
    "READ": "read",
}

# Device platforms
DEVICE_PLATFORMS = {
    "IOS": "ios",
    "ANDROID": "android",
    "WEB": "web",
}

# Common template variables
TEMPLATE_VARIABLES = {
    "USER_NAME": "{{ user.name }}",
    "FIRST_NAME": "{{ user.first_name }}",
    "PHONE_NUMBER": "{{ user.phone_number }}",
    "SHOP_NAME": "{{ shop.name }}",
    "SERVICE_NAME": "{{ service.name }}",
    "APPOINTMENT_DATE": '{{ appointment.start_time|date:"d M, Y" }}',
    "APPOINTMENT_TIME": '{{ appointment.start_time|time:"h:i A" }}',
    "SPECIALIST_NAME": "{{ specialist.employee.first_name }} {{ specialist.employee.last_name }}",
    "TICKET_NUMBER": "{{ ticket.ticket_number }}",
    "QUEUE_POSITION": "{{ ticket.position }}",
    "ESTIMATED_WAIT": "{{ ticket.estimated_wait_time }}",
    "VERIFICATION_CODE": "{{ code }}",
}
