from django.db.models import Avg, Count, Q
from django.utils import timezone

from apps.bookingapp.models import Appointment
from apps.queueapp.models import Queue, QueueTicket


class HybridQueueManager:
    """
    Manages the hybrid queue-appointment system, integrating scheduled appointments
    with walk-in queue customers.
    """

    @staticmethod
    def get_next_to_serve(shop_id, specialist_id=None):
        """
        Determine who should be served next, considering both appointments and queue.
        Prioritizes appointments at their scheduled time, but allows serving walk-ins
        during gaps or if appointments are late.
        """
        now = timezone.now()
        grace_period_minutes = 5  # Appointment grace period

        # Check for appointments that are due now (or slightly overdue within grace period)
        appointment_due_time_start = now - timezone.timedelta(
            minutes=grace_period_minutes
        )
        appointment_due_time_end = now + timezone.timedelta(
            minutes=15
        )  # Look ahead 15 minutes

        # Query filters for appointments
        appointment_filters = Q(
            shop_id=shop_id,
            status="scheduled",
            start_time__gte=appointment_due_time_start,
            start_time__lte=appointment_due_time_end,
        )

        # Add specialist filter if provided
        if specialist_id:
            appointment_filters &= Q(specialist_id=specialist_id)

        # Get due appointments sorted by scheduled time
        due_appointments = Appointment.objects.filter(appointment_filters).order_by(
            "start_time"
        )

        # If there's a due appointment, prioritize it
        if due_appointments.exists():
            return {"type": "appointment", "appointment": due_appointments.first()}

        # No due appointments, check queue for walk-ins
        queue_filters = Q(queue__shop_id=shop_id, status="waiting")

        # Add specialist filter if provided (if tickets have assigned specialists)
        if specialist_id:
            queue_filters &= Q(specialist_id=specialist_id) | Q(specialist_id=None)

        # Get next ticket in queue
        next_ticket = (
            QueueTicket.objects.filter(queue_filters).order_by("position").first()
        )

        if next_ticket:
            return {"type": "queue", "ticket": next_ticket}

        # Nothing to serve right now
        return {"type": "none", "message": "No appointments due or customers waiting"}

    @staticmethod
    def get_service_sequence(shop_id, time_window_start=None, time_window_end=None):
        """
        Generate a sequence of who to serve when, integrating both
        scheduled appointments and queue tickets.

        This helps staff plan their day by seeing the combined timeline.
        """
        now = timezone.now()

        # Default time window to next 4 hours if not specified
        if not time_window_start:
            time_window_start = now

        if not time_window_end:
            time_window_end = now + timezone.timedelta(hours=4)

        # Get all appointments in the time window
        appointments = Appointment.objects.filter(
            shop_id=shop_id,
            status="scheduled",
            start_time__gte=time_window_start,
            start_time__lte=time_window_end,
        ).order_by("start_time")

        # Get current queue tickets
        queue_tickets = QueueTicket.objects.filter(
            queue__shop_id=shop_id, status="waiting"
        ).order_by("position")

        # Build the service sequence
        service_sequence = []

        # Add all appointments with their exact times
        for appointment in appointments:
            service_sequence.append(
                {
                    "type": "appointment",
                    "id": appointment.id,
                    "time": appointment.start_time,
                    "customer_id": appointment.customer_id,
                    "service_id": appointment.service_id,
                    "specialist_id": appointment.specialist_id,
                    "duration": appointment.service.duration,
                }
            )

        # Calculate estimated times for queue tickets
        # unused_unused_current_time = now
        avg_service_time_minutes = 15  # Default if no data

        # Try to get a better estimate from recent service times
        recent_served = QueueTicket.objects.filter(
            queue__shop_id=shop_id,
            status="served",
            serve_time__isnull=False,
            complete_time__isnull=False,
        ).order_by("-complete_time")[:20]

        if recent_served:
            total_minutes = 0
            count = 0

            for ticket in recent_served:
                if ticket.serve_time and ticket.complete_time:
                    service_duration = (
                        ticket.complete_time - ticket.serve_time
                    ).total_seconds() / 60
                    if 0 < service_duration < 120:  # Ignore outliers
                        total_minutes += service_duration
                        count += 1

            if count > 0:
                avg_service_time_minutes = total_minutes / count

        # Calculate time gaps between appointments to fit in queue tickets
        appointment_gaps = []

        for i in range(len(service_sequence) - 1):
            current_end = service_sequence[i]["time"] + timezone.timedelta(
                minutes=service_sequence[i]["duration"]
            )
            next_start = service_sequence[i + 1]["time"]

            if next_start > current_end:
                # There's a gap
                gap_minutes = (next_start - current_end).total_seconds() / 60

                if gap_minutes >= avg_service_time_minutes:
                    appointment_gaps.append(
                        {
                            "start": current_end,
                            "end": next_start,
                            "minutes": gap_minutes,
                        }
                    )

        # Add an initial gap if first appointment is in the future
        if service_sequence and service_sequence[0]["time"] > now:
            gap_minutes = (service_sequence[0]["time"] - now).total_seconds() / 60
            if gap_minutes >= avg_service_time_minutes:
                appointment_gaps.insert(
                    0,
                    {
                        "start": now,
                        "end": service_sequence[0]["time"],
                        "minutes": gap_minutes,
                    },
                )

        # If no appointments or all appointments are in future, create a single gap from now
        if not appointment_gaps and (
            not service_sequence or service_sequence[0]["time"] > now
        ):
            appointment_gaps.append(
                {
                    "start": now,
                    "end": time_window_end,
                    "minutes": (time_window_end - now).total_seconds() / 60,
                }
            )

        # Fill gaps with queue tickets
        ticket_index = 0
        for gap in appointment_gaps:
            available_minutes = gap["minutes"]
            start_time = gap["start"]

            # How many tickets can we fit in this gap?
            while (
                available_minutes >= avg_service_time_minutes
                and ticket_index < queue_tickets.count()
            ):
                ticket = queue_tickets[ticket_index]

                service_sequence.append(
                    {
                        "type": "queue",
                        "id": ticket.id,
                        "time": start_time,
                        "customer_id": ticket.customer_id,
                        "service_id": ticket.service_id if ticket.service else None,
                        "ticket_number": ticket.ticket_number,
                        "position": ticket.position,
                        "estimated_duration": avg_service_time_minutes,
                    }
                )

                # Update for next iteration
                start_time = start_time + timezone.timedelta(
                    minutes=avg_service_time_minutes
                )
                available_minutes -= avg_service_time_minutes
                ticket_index += 1

        # Sort the final sequence by time
        service_sequence.sort(key=lambda x: x["time"])

        return service_sequence

    @staticmethod
    def handle_appointment_arrival(appointment_id):
        """
        Handle a scheduled appointment customer who has arrived.
        Automatically integrates them into the service flow.
        """
        try:
            appointment = Appointment.objects.get(id=appointment_id)

            # Check if the appointment is today
            now = timezone.now()
            appointment_date = appointment.start_time.date()
            today = now.date()

            if appointment_date != today:
                return {"error": "This appointment is not scheduled for today"}

            # Check if it's within a reasonable time window (±30 min of scheduled time)
            time_diff = (
                now - appointment.start_time
            ).total_seconds() / 60  # Minutes difference

            if abs(time_diff) > 30:
                # More than 30 minutes early or late
                # For very early arrivals, we may want to add them to the queue instead
                if time_diff < -30:  # More than 30 min early
                    # Add to queue with priority flag
                    from apps.queueapp.services.queue_service import QueueService

                    # Find appropriate queue for this shop
                    queue = Queue.objects.filter(shop=appointment.shop).first()

                    if queue:
                        # Join queue but with a priority position
                        return QueueService.join_queue(
                            queue.id,
                            appointment.customer.id,
                            appointment.service.id,
                            is_appointment=True,
                            appointment_id=appointment.id,
                        )
                    else:
                        return {"error": "No queue available for this shop"}

                elif time_diff > 30:  # More than 30 min late
                    # Still handle them, but note the lateness
                    appointment.notes += (
                        f"\nCustomer arrived {int(time_diff)} minutes late."
                    )
                    appointment.save()

            # Mark appointment as confirmed/arrived
            appointment.status = "confirmed"
            appointment.save()

            return {
                "success": True,
                "appointment": appointment,
                "message": "Customer has been marked as arrived",
            }

        except Appointment.DoesNotExist:
            return {"error": "Appointment not found"}

    @staticmethod
    def suggest_queue_management_actions(shop_id):
        """
        Analyzes current queue and appointments to suggest optimal actions
        for staff to keep things flowing smoothly.
        """
        now = timezone.now()

        # Get current queue state
        waiting_tickets = QueueTicket.objects.filter(
            queue__shop_id=shop_id, status="waiting"
        ).count()

        # Get upcoming appointments
        upcoming_appointments = Appointment.objects.filter(
            shop_id=shop_id,
            status="scheduled",
            start_time__gt=now,
            start_time__lte=now + timezone.timedelta(hours=2),
        ).count()

        # Get active staff count
        from apps.specialistsapp.models import Specialist

        active_specialists = Specialist.objects.filter(
            employee__shop_id=shop_id, employee__is_active=True
        ).count()

        # Calculate average service time
        served_today = QueueTicket.objects.filter(
            queue__shop_id=shop_id, status="served", join_time__date=now.date()
        )

        avg_wait_time = (
            served_today.aggregate(avg_wait=Avg("actual_wait_time"))["avg_wait"] or 0
        )

        # Build recommendations
        recommendations = []

        # Check if queue is building up too much
        if waiting_tickets > active_specialists * 5:
            recommendations.append(
                {
                    "type": "warning",
                    "message": f"Queue is building up ({waiting_tickets} waiting). Consider adding more staff or temporarily limiting new joins.",
                }
            )

        # Check if we're understaffed for upcoming appointments
        appointments_per_hour = upcoming_appointments / 2  # For the next 2 hours
        if appointments_per_hour > active_specialists * 3:
            recommendations.append(
                {
                    "type": "warning",
                    "message": f"High appointment load coming up ({upcoming_appointments} in next 2 hours). Consider adding more staff.",
                }
            )

        # Check if wait time is too high
        if avg_wait_time > 30:
            recommendations.append(
                {
                    "type": "warning",
                    "message": f"Average wait time is high ({int(avg_wait_time)} min). Consider optimizing service time or adding staff.",
                }
            )

        # Check if we're overstaffed
        if (
            active_specialists > 1
            and waiting_tickets == 0
            and upcoming_appointments < 3
        ):
            recommendations.append(
                {
                    "type": "optimization",
                    "message": "Currently overstaffed for demand. Consider reducing staff or using extra capacity for other tasks.",
                }
            )

        # Suggest redistributing specialists if needed
        if active_specialists > 1:
            # Check service distribution
            service_distribution = (
                QueueTicket.objects.filter(
                    queue__shop_id=shop_id, status="waiting", service__isnull=False
                )
                .values("service_id")
                .annotate(count=Count("id"))
            )

            if len(service_distribution) > 0:
                max_service = max(service_distribution, key=lambda x: x["count"])
                if max_service["count"] > 3:
                    recommendations.append(
                        {
                            "type": "optimization",
                            "message": f'High demand for specific service (ID: {max_service["service_id"]}). Consider assigning more specialists to this service.',
                        }
                    )

        return {
            "current_state": {
                "waiting_tickets": waiting_tickets,
                "upcoming_appointments": upcoming_appointments,
                "active_specialists": active_specialists,
                "avg_wait_time": avg_wait_time,
            },
            "recommendations": recommendations,
        }
