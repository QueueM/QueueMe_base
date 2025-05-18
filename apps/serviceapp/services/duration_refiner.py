from datetime import timedelta

from django.utils import timezone

from apps.bookingapp.models import Appointment
from apps.serviceapp.models import Service


class DurationRefiner:
    """
    Service that analyzes completed appointments to refine service durations

    This sophisticated algorithm learns from actual service delivery times
    to make scheduling more accurate over time.
    """

    @staticmethod
    def analyze_service_duration(service_id, lookback_days=30):
        """
        Analyze completed appointments for a service to determine actual duration

        Returns statistics about service duration including:
        - average_duration: The average time spent on the service
        - median_duration: The median duration (more robust to outliers)
        - p90_duration: The 90th percentile duration
        - recommended_duration: Suggested new duration
        - confidence: How confident we are in the recommendation
        """
        service = Service.objects.get(id=service_id)

        # Get completed appointments in the lookback period
        lookback_date = timezone.now() - timedelta(days=lookback_days)

        completed_appointments = Appointment.objects.filter(
            service=service,
            status="completed",
            start_time__gte=lookback_date,
            end_time__isnull=False,  # Ensure we have both start and end times
        )

        # Calculate actual durations
        duration_minutes = []
        for appointment in completed_appointments:
            # Calculate duration in minutes
            duration = (appointment.end_time - appointment.start_time).total_seconds() / 60

            # Filter out extreme outliers (e.g., system errors or cases where end time
            # was recorded much later)
            if 0 < duration < (service.duration * 3):  # Accept up to 3x the expected duration
                duration_minutes.append(duration)

        # If we don't have enough data, return with low confidence
        if len(duration_minutes) < 5:  # Need at least 5 data points
            return {
                "service_id": service_id,
                "current_duration": service.duration,
                "sample_size": len(duration_minutes),
                "confidence": "low",
                "recommendation": "Not enough data to make a recommendation",
            }

        # Calculate statistics
        import numpy as np

        avg_duration = np.mean(duration_minutes)
        median_duration = np.median(duration_minutes)
        p90_duration = np.percentile(duration_minutes, 90)
        std_deviation = np.std(duration_minutes)

        # Determine confidence based on sample size and consistency
        confidence_score = min(
            1.0, len(duration_minutes) / 50
        )  # Up to 50 samples for full confidence

        # Reduce confidence if high variation
        coefficient_of_variation = (
            std_deviation / avg_duration if avg_duration > 0 else float("inf")
        )
        if coefficient_of_variation > 0.3:  # More than 30% variation
            confidence_score *= 0.7

        # Determine confidence level
        if confidence_score > 0.8:
            confidence = "high"
        elif confidence_score > 0.5:
            confidence = "medium"
        else:
            confidence = "low"

        # Make a recommendation
        # For scheduling, using a higher percentile (like p90) is often better than the mean
        # to ensure most appointments finish on time
        recommended_duration = round(p90_duration)

        # Don't recommend changes smaller than 5 minutes
        if abs(recommended_duration - service.duration) < 5:
            recommendation = "No change needed"
            recommended_duration = service.duration
        else:
            if recommended_duration > service.duration:
                recommendation = f"Increase duration to {recommended_duration} minutes"
            else:
                recommendation = f"Decrease duration to {recommended_duration} minutes"

        return {
            "service_id": service_id,
            "current_duration": service.duration,
            "average_duration": round(avg_duration, 1),
            "median_duration": round(median_duration, 1),
            "p90_duration": round(p90_duration, 1),
            "std_deviation": round(std_deviation, 1),
            "sample_size": len(duration_minutes),
            "coefficient_of_variation": round(coefficient_of_variation, 2),
            "confidence": confidence,
            "confidence_score": round(confidence_score, 2),
            "recommended_duration": recommended_duration,
            "recommendation": recommendation,
        }

    @staticmethod
    def analyze_buffer_times(service_id, lookback_days=30):
        """
        Analyze if buffer times (before/after) need adjustment

        Returns recommendations for buffer times based on appointment data
        """
        service = Service.objects.get(id=service_id)

        # Get completed appointments in the lookback period
        lookback_date = timezone.now() - timedelta(days=lookback_days)

        # For buffer_before analysis, we need appointments with check_in time
        appointments_with_checkin = Appointment.objects.filter(
            service=service,
            status="completed",
            start_time__gte=lookback_date,
            check_in_time__isnull=False,  # We need check-in time to analyze prep time
        )

        # For buffer_after, we need appointments with next appointment start
        # This is more complex as we need to find the next appointment for each specialist
        completed_appointments = Appointment.objects.filter(
            service=service, status="completed", end_time__gte=lookback_date
        ).order_by("specialist", "end_time")

        # Calculate actual prep times (time between check-in and start)
        prep_times = []
        for appointment in appointments_with_checkin:
            if appointment.check_in_time < appointment.start_time:
                prep_time = (
                    appointment.start_time - appointment.check_in_time
                ).total_seconds() / 60
                if 0 < prep_time < 60:  # Reasonable prep time under 1 hour
                    prep_times.append(prep_time)

        # Calculate actual cleanup times (time between end and next appointment start)
        cleanup_times = []
        prev_specialist = None
        prev_appointment = None

        for appointment in completed_appointments:
            if prev_specialist == appointment.specialist and prev_appointment:
                # This is the next appointment for the same specialist
                cleanup_time = (
                    appointment.start_time - prev_appointment.end_time
                ).total_seconds() / 60
                if 0 < cleanup_time < 60:  # Reasonable cleanup time under 1 hour
                    cleanup_times.append(cleanup_time)

            prev_specialist = appointment.specialist
            prev_appointment = appointment

        # Analyze results
        results = {
            "service_id": service_id,
            "current_buffer_before": service.buffer_before,
            "current_buffer_after": service.buffer_after,
        }

        # Analyze prep times if we have enough data
        if len(prep_times) >= 5:
            import numpy as np

            avg_prep = np.mean(prep_times)
            median_prep = np.median(prep_times)
            p90_prep = np.percentile(prep_times, 90)

            results.update(
                {
                    "prep_time_sample_size": len(prep_times),
                    "average_prep_time": round(avg_prep, 1),
                    "median_prep_time": round(median_prep, 1),
                    "p90_prep_time": round(p90_prep, 1),
                }
            )

            # Make recommendation for buffer_before
            recommended_before = round(p90_prep)

            if abs(recommended_before - service.buffer_before) >= 5:
                if recommended_before > service.buffer_before:
                    results[
                        "buffer_before_recommendation"
                    ] = f"Increase to {recommended_before} minutes"
                else:
                    results[
                        "buffer_before_recommendation"
                    ] = f"Decrease to {recommended_before} minutes"
                results["recommended_buffer_before"] = recommended_before
            else:
                results["buffer_before_recommendation"] = "No change needed"
                results["recommended_buffer_before"] = service.buffer_before
        else:
            results["prep_time_sample_size"] = len(prep_times)
            results["buffer_before_recommendation"] = "Not enough data"

        # Analyze cleanup times if we have enough data
        if len(cleanup_times) >= 5:
            import numpy as np

            avg_cleanup = np.mean(cleanup_times)
            median_cleanup = np.median(cleanup_times)
            p90_cleanup = np.percentile(cleanup_times, 90)

            results.update(
                {
                    "cleanup_time_sample_size": len(cleanup_times),
                    "average_cleanup_time": round(avg_cleanup, 1),
                    "median_cleanup_time": round(median_cleanup, 1),
                    "p90_cleanup_time": round(p90_cleanup, 1),
                }
            )

            # Make recommendation for buffer_after
            recommended_after = round(p90_cleanup)

            if abs(recommended_after - service.buffer_after) >= 5:
                if recommended_after > service.buffer_after:
                    results[
                        "buffer_after_recommendation"
                    ] = f"Increase to {recommended_after} minutes"
                else:
                    results[
                        "buffer_after_recommendation"
                    ] = f"Decrease to {recommended_after} minutes"
                results["recommended_buffer_after"] = recommended_after
            else:
                results["buffer_after_recommendation"] = "No change needed"
                results["recommended_buffer_after"] = service.buffer_after
        else:
            results["cleanup_time_sample_size"] = len(cleanup_times)
            results["buffer_after_recommendation"] = "Not enough data"

        return results

    @staticmethod
    def apply_recommended_duration(service_id, new_duration):
        """Apply a recommended duration to a service"""
        service = Service.objects.get(id=service_id)
        service.duration = new_duration
        service.save()
        return service

    @staticmethod
    def apply_recommended_buffer_times(service_id, buffer_before=None, buffer_after=None):
        """Apply recommended buffer times to a service"""
        service = Service.objects.get(id=service_id)

        if buffer_before is not None:
            service.buffer_before = buffer_before

        if buffer_after is not None:
            service.buffer_after = buffer_after

        service.save()
        return service
