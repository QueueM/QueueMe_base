# apps/bookingapp/services/specialist_matcher.py
from datetime import datetime

from django.db.models import Avg

from apps.bookingapp.models import Appointment
from apps.reviewapp.models import Review
from apps.specialistsapp.models import Specialist


class SpecialistMatcher:
    """Advanced service for matching customers with the optimal specialist"""

    @staticmethod
    def find_best_specialist(service_id, customer_id=None, time_slot=None):
        """
        Find the optimal specialist for a service based on multiple factors

        Args:
            service_id: UUID of the service
            customer_id: Optional UUID of customer (for personalization)
            time_slot: Optional tuple (start_datetime, end_datetime)

        Returns:
            Specialist object or None if no match found
        """
        # Get specialists qualified for this service
        specialists = Specialist.objects.filter(
            specialist_services__service_id=service_id
        )

        # If time slot provided, filter by availability
        if time_slot:
            start_time, end_time = time_slot
            available_specialists = []

            from apps.bookingapp.services.availability_service import (
                AvailabilityService,
            )

            for specialist in specialists:
                if AvailabilityService.is_specialist_available(
                    specialist,
                    start_time.date(),
                    start_time.time(),
                    end_time.time(),
                    0,  # We'll add buffer times later
                    0,  # We'll add buffer times later
                ):
                    available_specialists.append(specialist.id)

            specialists = specialists.filter(id__in=available_specialists)

        # If no specialists available, return None
        if not specialists.exists():
            return None

        # Calculate workload score (specialists with fewer appointments ranked higher)
        # Get appointment counts for today
        today = datetime.now().date()
        appointment_counts = {}

        for specialist in specialists:
            count = Appointment.objects.filter(
                specialist=specialist,
                start_time__date=today,
                status__in=["scheduled", "confirmed", "in_progress"],
            ).count()
            appointment_counts[specialist.id] = count

        # Calculate ratings
        specialist_ratings = {}
        for specialist in specialists:
            avg_rating = (
                Review.objects.filter(
                    content_type__model="specialist", object_id=specialist.id
                ).aggregate(avg=Avg("rating"))["avg"]
                or 3.0
            )  # Default if no ratings

            specialist_ratings[specialist.id] = avg_rating

        # If customer provided, check for previous appointments
        customer_history = {}
        if customer_id:
            for specialist in specialists:
                previous_appointments = Appointment.objects.filter(
                    specialist=specialist, customer_id=customer_id, status="completed"
                ).count()

                customer_history[specialist.id] = previous_appointments

        # Calculate final scores
        scores = {}

        # Define weights for each factor
        WORKLOAD_WEIGHT = 0.3
        RATING_WEIGHT = 0.4
        HISTORY_WEIGHT = 0.3

        max_appointments = max(appointment_counts.values()) if appointment_counts else 1

        for specialist in specialists:
            # Normalize workload (fewer appointments = higher score)
            if max_appointments > 0:
                workload_score = 1 - (
                    appointment_counts.get(specialist.id, 0) / max_appointments
                )
            else:
                workload_score = 1

            # Rating score (higher is better)
            rating_score = specialist_ratings.get(specialist.id, 3.0) / 5.0

            # Customer history score (higher is better)
            if customer_id:
                history_count = customer_history.get(specialist.id, 0)
                # Cap at 3 for normalization (more than 3 previous appointments = perfect score)
                history_score = min(history_count, 3) / 3.0
            else:
                history_score = 0

            # Calculate final score
            final_score = (
                (workload_score * WORKLOAD_WEIGHT)
                + (rating_score * RATING_WEIGHT)
                + (history_score * HISTORY_WEIGHT)
            )

            scores[specialist.id] = final_score

        # Find specialist with highest score
        if scores:
            best_specialist_id = max(scores.items(), key=lambda x: x[1])[0]
            return Specialist.objects.get(id=best_specialist_id)

        # Fallback: return first available specialist
        return specialists.first()
