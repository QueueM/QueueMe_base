from django.contrib import admin

from .models import Queue, QueueTicket


class QueueAdmin(admin.ModelAdmin):
    list_display = ("name", "shop", "status", "max_capacity", "created_at")
    list_filter = ("status", "shop")
    search_fields = ("name", "shop__name")
    date_hierarchy = "created_at"


class QueueTicketAdmin(admin.ModelAdmin):
    list_display = (
        "ticket_number",
        "queue",
        "customer",
        "status",
        "position",
        "estimated_wait_time",
        "join_time",
    )
    list_filter = ("status", "queue", "queue__shop")
    search_fields = ("ticket_number", "customer__phone_number", "queue__name")
    date_hierarchy = "join_time"
    readonly_fields = (
        "ticket_number",
        "join_time",
        "called_time",
        "serve_time",
        "complete_time",
    )


admin.site.register(Queue, QueueAdmin)
admin.site.register(QueueTicket, QueueTicketAdmin)
