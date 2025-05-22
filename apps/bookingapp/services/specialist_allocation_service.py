"""
Specialist Allocation Service

A service for optimally allocating specialists to appointments based on
various criteria such as workload balancing, specialist skills, customer preferences,
and waiting time optimization.

Key features:
1. Workload balancing across specialists
2. Customer-specialist matching and preference handling
3. Skill-based allocation
4. Wait time optimization
5. Specialist performance metrics
"""

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.db import transaction
from django.db.models import (
    Avg,
    Count,
)
from django.utils import timezone

from apps.bookingapp.models import Appointment
from apps.customersapp.models import CustomerSpecialistPreference
from apps.serviceapp.models import Service, ServiceRequirement
from apps.specialistsapp.models import Specialist, SpecialistSkill

logger = logging.getLogger(__name__)

# Type definitions
SpecialistScore = Dict[str, float]  # Mapping of specialist ID to score
AllocationResult = Dict[str, Any]  # Result of allocation operation


class SpecialistAllocationService:
    """
    Service for allocating the most suitable specialists to appointments
    based on multiple criteria and optimization strategies.
    """

    # Weight constants for scoring algorithms
    WEIGHT_WORKLOAD = 0.30  # Importance of balanced workload
    WEIGHT_SKILLS = 0.25  # Importance of specialist's skill level
    WEIGHT_CUSTOMER_PREFERENCE = 0.20  # Importance of customer preference
    WEIGHT_WAITING_TIME = 0.15  # Importance of minimizing wait time
    WEIGHT_PERFORMANCE = 0.10  # Importance of specialist performance

    @classmethod
    def find_optimal_specialist(
        cls,
        service_id: str,
        shop_id: str,
        appointment_datetime: datetime,
        customer_id: Optional[str] = None,
        required_skills: Optional[List[str]] = None,
    ) -> AllocationResult:
        """
        Find the optimal specialist for a given service and time.

        Args:
            service_id: ID of the service
            shop_id: ID of the shop
            appointment_datetime: Datetime of the appointment
            customer_id: Optional customer ID for preference matching
            required_skills: Optional list of required skill IDs

        Returns:
            Dict with allocation result and specialist details
        """
        try:
            # Get all specialists who can perform this service
            eligible_specialists = cls._get_eligible_specialists(
                service_id=service_id,
                shop_id=shop_id,
                appointment_datetime=appointment_datetime,
                required_skills=required_skills,
            )

            if not eligible_specialists:
                return {
                    "success": False,
                    "message": "No eligible specialists available for this service at the requested time",
                    "specialists": [],
                }

            # Calculate scores for each specialist based on multiple criteria
            specialist_scores = {}

            # Get workload distribution for scoring
            workload_scores = cls._calculate_workload_scores(
                specialist_ids=[str(s.id) for s in eligible_specialists],
                appointment_date=appointment_datetime.date(),
            )

            # Get skill level scores
            skill_scores = cls._calculate_skill_scores(
                specialist_ids=[str(s.id) for s in eligible_specialists],
                service_id=service_id,
                required_skills=required_skills,
            )

            # Get customer preference scores if customer provided
            preference_scores = {}
            if customer_id:
                preference_scores = cls._calculate_preference_scores(
                    specialist_ids=[str(s.id) for s in eligible_specialists],
                    customer_id=customer_id,
                )

            # Get waiting time scores
            waiting_time_scores = cls._calculate_waiting_time_scores(
                specialist_ids=[str(s.id) for s in eligible_specialists],
                service_id=service_id,
                shop_id=shop_id,
            )

            # Get performance scores
            performance_scores = cls._calculate_performance_scores(
                specialist_ids=[str(s.id) for s in eligible_specialists],
                service_id=service_id,
            )

            # Calculate overall scores with weighted factors
            for specialist in eligible_specialists:
                specialist_id = str(specialist.id)

                # Combine all scoring factors with weights
                overall_score = (
                    workload_scores.get(specialist_id, 0.0) * cls.WEIGHT_WORKLOAD
                    + skill_scores.get(specialist_id, 0.0) * cls.WEIGHT_SKILLS
                    + preference_scores.get(specialist_id, 0.0)
                    * cls.WEIGHT_CUSTOMER_PREFERENCE
                    + waiting_time_scores.get(specialist_id, 0.0)
                    * cls.WEIGHT_WAITING_TIME
                    + performance_scores.get(specialist_id, 0.0)
                    * cls.WEIGHT_PERFORMANCE
                )

                specialist_scores[specialist_id] = overall_score

            # Sort specialists by score (highest first)
            sorted_specialists = sorted(
                specialist_scores.items(), key=lambda x: x[1], reverse=True
            )

            # Get detailed information for the top specialists
            top_specialists = []
            for specialist_id, score in sorted_specialists[:3]:  # Return top 3
                specialist = next(
                    s for s in eligible_specialists if str(s.id) == specialist_id
                )

                top_specialists.append(
                    {
                        "specialist_id": specialist_id,
                        "name": (
                            specialist.employee.name
                            if hasattr(specialist, "employee")
                            else "Unknown"
                        ),
                        "score": score,
                        "workload_score": workload_scores.get(specialist_id, 0.0),
                        "skill_score": skill_scores.get(specialist_id, 0.0),
                        "preference_score": preference_scores.get(specialist_id, 0.0),
                        "waiting_time_score": waiting_time_scores.get(
                            specialist_id, 0.0
                        ),
                        "performance_score": performance_scores.get(specialist_id, 0.0),
                    }
                )

            # Return the best specialist
            if sorted_specialists:
                best_specialist_id = sorted_specialists[0][0]
                best_specialist = next(
                    s for s in eligible_specialists if str(s.id) == best_specialist_id
                )

                return {
                    "success": True,
                    "message": "Optimal specialist found",
                    "specialist_id": best_specialist_id,
                    "specialist_name": (
                        best_specialist.employee.name
                        if hasattr(best_specialist, "employee")
                        else "Unknown"
                    ),
                    "score": sorted_specialists[0][1],
                    "all_specialists": top_specialists,
                }
            else:
                return {
                    "success": False,
                    "message": "Could not determine optimal specialist",
                    "specialists": [],
                }

        except Exception as e:
            logger.error(f"Error finding optimal specialist: {str(e)}")
            return {
                "success": False,
                "message": f"Error finding optimal specialist: {str(e)}",
                "specialists": [],
            }

    @classmethod
    def optimize_specialist_assignments(
        cls, shop_id: str, date_to_optimize: date, rebalance_existing: bool = False
    ) -> AllocationResult:
        """
        Optimize specialist assignments for all appointments on a given day.

        Args:
            shop_id: ID of the shop
            date_to_optimize: Date to optimize assignments for
            rebalance_existing: Whether to rebalance existing confirmed appointments

        Returns:
            Dict with optimization results
        """
        try:
            # Get all appointments for this day that need specialists
            day_start = datetime.combine(date_to_optimize, datetime.min.time())
            day_end = datetime.combine(date_to_optimize, datetime.max.time())

            # Define which statuses to include
            statuses_to_include = ["scheduled"]
            if rebalance_existing:
                statuses_to_include.append("confirmed")

            appointments = Appointment.objects.filter(
                shop_id=shop_id,
                start_time__gte=day_start,
                start_time__lt=day_end,
                status__in=statuses_to_include,
            ).order_by("start_time")

            if not appointments:
                return {
                    "success": True,
                    "message": "No appointments to optimize",
                    "updated_count": 0,
                }

            # Get all specialists for this shop
            shop_specialists = Specialist.objects.filter(
                employee__company__shops=shop_id, is_active=True
            )

            if not shop_specialists:
                return {
                    "success": False,
                    "message": "No active specialists found for this shop",
                    "updated_count": 0,
                }

            # Track current workload for each specialist
            specialist_workload = {str(s.id): 0 for s in shop_specialists}
            updates_made = 0

            with transaction.atomic():
                # Process appointments in order
                for appointment in appointments:
                    # Find the optimal specialist for this service
                    optimal_result = cls.find_optimal_specialist(
                        service_id=str(appointment.service_id),
                        shop_id=shop_id,
                        appointment_datetime=appointment.start_time,
                        customer_id=(
                            str(appointment.customer_id)
                            if appointment.customer
                            else None
                        ),
                    )

                    if optimal_result["success"]:
                        best_specialist_id = optimal_result["specialist_id"]

                        # Update the appointment if specialist different
                        if str(appointment.specialist_id) != best_specialist_id:
                            appointment.specialist_id = best_specialist_id
                            appointment.last_modified = timezone.now()
                            appointment.save()
                            updates_made += 1

                        # Update workload tracking
                        specialist_workload[best_specialist_id] = (
                            specialist_workload.get(best_specialist_id, 0) + 1
                        )

            return {
                "success": True,
                "message": f"Successfully optimized {updates_made} specialist assignments",
                "updated_count": updates_made,
                "total_appointments": appointments.count(),
                "workload_distribution": specialist_workload,
            }

        except Exception as e:
            logger.error(f"Error optimizing specialist assignments: {str(e)}")
            return {
                "success": False,
                "message": f"Error optimizing specialist assignments: {str(e)}",
                "updated_count": 0,
            }

    @classmethod
    def get_specialist_availability_forecast(
        cls, specialist_id: str, start_date: date, days: int = 7
    ) -> Dict[str, Any]:
        """
        Get a forecast of specialist availability over a period of days.

        Args:
            specialist_id: ID of the specialist
            start_date: Start date for the forecast
            days: Number of days to forecast

        Returns:
            Dict with availability forecast by day and hour
        """
        try:
            specialist = Specialist.objects.get(id=specialist_id)

            # Calculate end date
            end_date = start_date + timedelta(days=days)

            # Get all appointments in the date range
            appointments = Appointment.objects.filter(
                specialist_id=specialist_id,
                start_time__gte=datetime.combine(start_date, datetime.min.time()),
                start_time__lt=datetime.combine(end_date, datetime.min.time()),
                status__in=["scheduled", "confirmed", "in_progress"],
            ).order_by("start_time")

            # Initialize availability data structure
            availability = {}

            # Iterate through each day in the range
            current_date = start_date
            while current_date < end_date:
                day_data = {
                    "date": current_date.isoformat(),
                    "day_of_week": current_date.weekday(),
                    "total_hours": 0,
                    "booked_hours": 0,
                    "available_hours": 0,
                    "utilization_percentage": 0,
                    "hourly_availability": {},
                    "appointments": [],
                }

                # Get working hours for this day
                working_hours = cls._get_specialist_working_hours(
                    specialist_id=specialist_id, day_of_week=current_date.weekday()
                )

                # If specialist doesn't work on this day, set all to 0
                if not working_hours:
                    availability[current_date.isoformat()] = day_data
                    current_date += timedelta(days=1)
                    continue

                # Calculate total working hours
                total_minutes = 0
                for start, end in working_hours:
                    start_minutes = start.hour * 60 + start.minute
                    end_minutes = end.hour * 60 + end.minute
                    total_minutes += end_minutes - start_minutes

                day_data["total_hours"] = round(total_minutes / 60, 1)

                # Get appointments for this day
                day_appointments = [
                    a for a in appointments if a.start_time.date() == current_date
                ]

                # Calculate booked hours
                booked_minutes = 0
                for appt in day_appointments:
                    duration = (appt.end_time - appt.start_time).total_seconds() / 60
                    booked_minutes += duration

                    # Add to appointments list
                    day_data["appointments"].append(
                        {
                            "appointment_id": str(appt.id),
                            "service_name": appt.service.name,
                            "start_time": appt.start_time.isoformat(),
                            "end_time": appt.end_time.isoformat(),
                            "duration_minutes": duration,
                        }
                    )

                day_data["booked_hours"] = round(booked_minutes / 60, 1)
                day_data["available_hours"] = round(
                    (total_minutes - booked_minutes) / 60, 1
                )

                if total_minutes > 0:
                    day_data["utilization_percentage"] = round(
                        (booked_minutes / total_minutes) * 100, 1
                    )

                # Calculate hourly availability
                hourly_data = cls._calculate_hourly_availability(
                    working_hours=working_hours, appointments=day_appointments
                )

                day_data["hourly_availability"] = hourly_data

                # Store data for this day
                availability[current_date.isoformat()] = day_data

                # Move to next day
                current_date += timedelta(days=1)

            return {
                "specialist_id": specialist_id,
                "name": (
                    specialist.employee.name
                    if hasattr(specialist, "employee")
                    else "Unknown"
                ),
                "start_date": start_date.isoformat(),
                "end_date": (end_date - timedelta(days=1)).isoformat(),
                "days": days,
                "daily_availability": availability,
            }

        except Exception as e:
            logger.error(f"Error getting specialist availability forecast: {str(e)}")
            return {
                "specialist_id": specialist_id,
                "error": str(e),
                "daily_availability": {},
            }

    # ------------------------------------------------------------------------
    # Private helper methods
    # ------------------------------------------------------------------------

    @staticmethod
    def _get_eligible_specialists(
        service_id: str,
        shop_id: str,
        appointment_datetime: datetime,
        required_skills: Optional[List[str]] = None,
    ) -> List[Specialist]:
        """
        Get specialists eligible for a service at a specific time.

        Args:
            service_id: ID of the service
            shop_id: ID of the shop
            appointment_datetime: Datetime of the appointment
            required_skills: Optional list of required skill IDs

        Returns:
            List of eligible specialist objects
        """
        try:
            # Get all specialists who can perform this service
            service_specialists = Specialist.objects.filter(
                specialist_services__service_id=service_id,
                employee__company__shops=shop_id,
                is_active=True,
            ).select_related("employee")

            if not service_specialists:
                return []

            # Filter by working hours
            day_of_week = appointment_datetime.weekday()
            working_specialists = []

            for specialist in service_specialists:
                # Check if specialist is working at this time
                working_hours = (
                    SpecialistAllocationService._get_specialist_working_hours(
                        specialist_id=str(specialist.id), day_of_week=day_of_week
                    )
                )

                if not working_hours:
                    continue

                # Check if appointment time falls within working hours
                appointment_time = appointment_datetime.time()
                is_working = False

                for start_time, end_time in working_hours:
                    if start_time <= appointment_time <= end_time:
                        is_working = True
                        break

                if is_working:
                    working_specialists.append(specialist)

            if not working_specialists:
                return []

            # Filter by existing appointments (availability)
            available_specialists = []
            service = Service.objects.get(id=service_id)

            # Calculate appointment duration with buffers
            buffer_before = service.buffer_before or 0
            buffer_after = service.buffer_after or 0

            appointment_start = appointment_datetime - timedelta(minutes=buffer_before)
            appointment_end = appointment_datetime + timedelta(
                minutes=service.duration + buffer_after
            )

            for specialist in working_specialists:
                # Check for overlapping appointments
                overlapping = Appointment.objects.filter(
                    specialist_id=specialist.id,
                    start_time__lt=appointment_end,
                    end_time__gt=appointment_start,
                    status__in=["scheduled", "confirmed", "in_progress"],
                ).exists()

                if not overlapping:
                    available_specialists.append(specialist)

            if not available_specialists:
                return []

            # Filter by required skills if specified
            if required_skills and len(required_skills) > 0:
                skilled_specialists = []

                for specialist in available_specialists:
                    # Check if specialist has all required skills
                    specialist_skills = SpecialistSkill.objects.filter(
                        specialist=specialist, skill_id__in=required_skills
                    ).values_list("skill_id", flat=True)

                    # Convert to set for efficient comparison
                    specialist_skill_set = set(
                        str(skill_id) for skill_id in specialist_skills
                    )
                    required_skill_set = set(required_skills)

                    # Specialist must have all required skills
                    if required_skill_set.issubset(specialist_skill_set):
                        skilled_specialists.append(specialist)

                return skilled_specialists

            return available_specialists

        except Exception as e:
            logger.error(f"Error getting eligible specialists: {str(e)}")
            return []

    @staticmethod
    def _calculate_workload_scores(
        specialist_ids: List[str], appointment_date: date
    ) -> SpecialistScore:
        """
        Calculate workload balance scores for specialists.

        Lower workload gets higher score (inverse relationship).

        Args:
            specialist_ids: List of specialist IDs
            appointment_date: Date of the appointment

        Returns:
            Dict mapping specialist IDs to workload scores
        """
        try:
            # Get appointment counts for each specialist on this day
            day_start = datetime.combine(appointment_date, datetime.min.time())
            day_end = datetime.combine(appointment_date, datetime.max.time())

            specialist_counts = defaultdict(int)

            appointments = (
                Appointment.objects.filter(
                    specialist_id__in=specialist_ids,
                    start_time__gte=day_start,
                    start_time__lt=day_end,
                    status__in=["scheduled", "confirmed", "in_progress"],
                )
                .values("specialist_id")
                .annotate(count=Count("id"))
            )

            # Convert to dict
            for item in appointments:
                specialist_counts[str(item["specialist_id"])] = item["count"]

            # Find min and max counts
            if not specialist_counts:
                # If no appointments yet, all specialists get top score
                return {specialist_id: 1.0 for specialist_id in specialist_ids}

            counts = list(specialist_counts.values())
            min_count = min(counts) if counts else 0
            max_count = max(counts) if counts else 0

            # Calculate scores - inverse relationship to workload
            # Higher workload = lower score
            scores = {}

            if max_count == min_count:  # All specialists have same workload
                return {specialist_id: 1.0 for specialist_id in specialist_ids}

            for specialist_id in specialist_ids:
                count = specialist_counts.get(specialist_id, 0)

                # Normalize to 0-1 range and invert
                # 0 appointments = 1.0 score
                # max appointments = 0.0 score
                if max_count > 0:
                    scores[specialist_id] = 1.0 - (count - min_count) / (
                        max_count - min_count
                    )
                else:
                    scores[specialist_id] = 1.0

            return scores

        except Exception as e:
            logger.error(f"Error calculating workload scores: {str(e)}")
            return {
                specialist_id: 0.5 for specialist_id in specialist_ids
            }  # Default to neutral score

    @staticmethod
    def _calculate_skill_scores(
        specialist_ids: List[str],
        service_id: str,
        required_skills: Optional[List[str]] = None,
    ) -> SpecialistScore:
        """
        Calculate skill-based scores for specialists.

        Args:
            specialist_ids: List of specialist IDs
            service_id: ID of the service
            required_skills: Optional list of required skill IDs

        Returns:
            Dict mapping specialist IDs to skill scores
        """
        try:
            scores = {}

            # Get service requirements if no specific skills provided
            if not required_skills:
                service_requirements = ServiceRequirement.objects.filter(
                    service_id=service_id
                ).select_related("skill")

                required_skills = [str(req.skill_id) for req in service_requirements]

            # If no specific skills required, all specialists get same score
            if not required_skills:
                return {
                    specialist_id: 0.8 for specialist_id in specialist_ids
                }  # Good default

            # Get all specialists' skills and proficiency levels
            specialist_skills = SpecialistSkill.objects.filter(
                specialist_id__in=specialist_ids, skill_id__in=required_skills
            ).select_related("skill")

            # Group by specialist
            skill_map = defaultdict(dict)

            for skill in specialist_skills:
                specialist_id = str(skill.specialist_id)
                skill_id = str(skill.skill_id)
                proficiency = (
                    skill.proficiency_level or 3
                )  # Default to medium if not set

                skill_map[specialist_id][skill_id] = proficiency

            # Calculate scores based on required skills
            for specialist_id in specialist_ids:
                specialist_skill_map = skill_map.get(specialist_id, {})
                total_skills = len(required_skills)

                if total_skills == 0:
                    scores[specialist_id] = 1.0  # No skills required
                    continue

                # Calculate score based on coverage and proficiency
                covered_skills = 0
                total_proficiency = 0

                for skill_id in required_skills:
                    if skill_id in specialist_skill_map:
                        covered_skills += 1
                        total_proficiency += specialist_skill_map[skill_id]

                # Coverage score (0-0.5)
                coverage_score = (covered_skills / total_skills) * 0.5

                # Proficiency score (0-0.5)
                max_possible_proficiency = total_skills * 5  # 5 is max proficiency
                proficiency_score = 0

                if covered_skills > 0:
                    proficiency_score = (
                        total_proficiency / max_possible_proficiency
                    ) * 0.5

                # Combined score
                scores[specialist_id] = coverage_score + proficiency_score

            return scores

        except Exception as e:
            logger.error(f"Error calculating skill scores: {str(e)}")
            return {
                specialist_id: 0.5 for specialist_id in specialist_ids
            }  # Default to neutral score

    @staticmethod
    def _calculate_preference_scores(
        specialist_ids: List[str], customer_id: str
    ) -> SpecialistScore:
        """
        Calculate scores based on customer preferences.

        Args:
            specialist_ids: List of specialist IDs
            customer_id: ID of the customer

        Returns:
            Dict mapping specialist IDs to preference scores
        """
        try:
            # Get customer's specialist preferences
            preferences = CustomerSpecialistPreference.objects.filter(
                customer_id=customer_id, specialist_id__in=specialist_ids
            )

            # Default score for specialists without specific preference
            default_score = 0.5

            # Initialize all with default
            scores = {specialist_id: default_score for specialist_id in specialist_ids}

            # Process explicit preferences
            for pref in preferences:
                specialist_id = str(pref.specialist_id)
                rating = pref.rating or 3  # Default to neutral if not set

                # Convert 1-5 rating to 0-1 score
                scores[specialist_id] = rating / 5.0

            # Boost preferred specialists, penalize disliked ones
            preferred_specialists = CustomerSpecialistPreference.objects.filter(
                customer_id=customer_id,
                is_preferred=True,
                specialist_id__in=specialist_ids,
            ).values_list("specialist_id", flat=True)

            disliked_specialists = CustomerSpecialistPreference.objects.filter(
                customer_id=customer_id,
                is_disliked=True,
                specialist_id__in=specialist_ids,
            ).values_list("specialist_id", flat=True)

            # Apply bonuses/penalties
            for specialist_id in specialist_ids:
                if str(specialist_id) in preferred_specialists:
                    scores[specialist_id] = min(1.0, scores[specialist_id] + 0.2)

                if str(specialist_id) in disliked_specialists:
                    scores[specialist_id] = max(0.0, scores[specialist_id] - 0.3)

            return scores

        except Exception as e:
            logger.error(f"Error calculating preference scores: {str(e)}")
            return {
                specialist_id: 0.5 for specialist_id in specialist_ids
            }  # Default to neutral score

    @staticmethod
    def _calculate_waiting_time_scores(
        specialist_ids: List[str], service_id: str, shop_id: str
    ) -> SpecialistScore:
        """
        Calculate scores based on waiting times for specialists.

        Args:
            specialist_ids: List of specialist IDs
            service_id: ID of the service
            shop_id: ID of the shop

        Returns:
            Dict mapping specialist IDs to waiting time scores
        """
        try:
            # Calculate average wait times for each specialist
            # based on completed appointments in the last 30 days
            thirty_days_ago = timezone.now() - timedelta(days=30)

            wait_times = {}
            max_wait = 0
            min_wait = float("inf")

            for specialist_id in specialist_ids:
                # Get completed appointments for this specialist and service
                completed_appointments = Appointment.objects.filter(
                    specialist_id=specialist_id,
                    service_id=service_id,
                    shop_id=shop_id,
                    status="completed",
                    end_time__gte=thirty_days_ago,
                )

                if not completed_appointments.exists():
                    # No data, use neutral score
                    wait_times[specialist_id] = None
                    continue

                # Calculate average wait time (difference between scheduled start and actual start)
                total_wait = 0
                count = 0

                for appt in completed_appointments:
                    if appt.scheduled_start_time and appt.actual_start_time:
                        wait_minutes = (
                            appt.actual_start_time - appt.scheduled_start_time
                        ).total_seconds() / 60

                        # Only consider reasonable wait times (< 120 minutes)
                        if 0 <= wait_minutes < 120:
                            total_wait += wait_minutes
                            count += 1

                if count > 0:
                    avg_wait = total_wait / count
                    wait_times[specialist_id] = avg_wait

                    # Track min/max for normalization
                    max_wait = max(max_wait, avg_wait)
                    min_wait = min(min_wait, avg_wait)
                else:
                    wait_times[specialist_id] = None

            # Convert to scores (lower wait time = higher score)
            scores = {}

            # If no valid wait times, use neutral scores
            if max_wait == 0 or min_wait == float("inf") or max_wait == min_wait:
                return {specialist_id: 0.7 for specialist_id in specialist_ids}

            for specialist_id in specialist_ids:
                wait_time = wait_times.get(specialist_id)

                if wait_time is None:
                    # No data, use slightly above average score
                    scores[specialist_id] = 0.6
                else:
                    # Normalize to 0-1 range and invert (lower wait = higher score)
                    scores[specialist_id] = 1.0 - (wait_time - min_wait) / (
                        max_wait - min_wait
                    )

            return scores

        except Exception as e:
            logger.error(f"Error calculating waiting time scores: {str(e)}")
            return {
                specialist_id: 0.5 for specialist_id in specialist_ids
            }  # Default to neutral score

    @staticmethod
    def _calculate_performance_scores(
        specialist_ids: List[str], service_id: str
    ) -> SpecialistScore:
        """
        Calculate scores based on specialist performance metrics.

        Args:
            specialist_ids: List of specialist IDs
            service_id: ID of the service

        Returns:
            Dict mapping specialist IDs to performance scores
        """
        try:
            # Calculate performance based on ratings, completion time,
            # and consistency over the last 90 days
            ninety_days_ago = timezone.now() - timedelta(days=90)

            scores = {}

            for specialist_id in specialist_ids:
                # Get completed appointments for this specialist and service
                completed_appointments = Appointment.objects.filter(
                    specialist_id=specialist_id,
                    service_id=service_id,
                    status="completed",
                    end_time__gte=ninety_days_ago,
                )

                if not completed_appointments.exists():
                    # No data, use neutral score
                    scores[specialist_id] = 0.6  # Slightly above average
                    continue

                # Calculate average rating
                rated_appointments = completed_appointments.exclude(rating__isnull=True)

                avg_rating = 0
                if rated_appointments.exists():
                    avg_rating = (
                        rated_appointments.aggregate(Avg("rating"))["rating__avg"] or 0
                    )

                # Normalize rating to 0-0.5 range
                rating_score = (avg_rating / 5.0) * 0.5

                # Calculate completion time efficiency
                efficiency_score = 0
                service = Service.objects.get(id=service_id)
                expected_duration = service.duration

                duration_appointments = completed_appointments.filter(
                    actual_start_time__isnull=False, actual_end_time__isnull=False
                )

                if duration_appointments.exists():
                    total_efficiency = 0
                    count = 0

                    for appt in duration_appointments:
                        actual_duration = (
                            appt.actual_end_time - appt.actual_start_time
                        ).total_seconds() / 60

                        # Only consider reasonable durations
                        if 0 < actual_duration < expected_duration * 2:
                            # Efficiency ratio (closer to 1 is better)
                            efficiency_ratio = expected_duration / actual_duration
                            total_efficiency += min(
                                efficiency_ratio, 1.5
                            )  # Cap at 150%
                            count += 1

                    if count > 0:
                        avg_efficiency = total_efficiency / count
                        # Normalize to 0-0.5 range (0.67 to 1.5 efficiency)
                        efficiency_score = min(
                            0.5, (avg_efficiency - 0.67) / (1.5 - 0.67) * 0.5
                        )

                # Combined score
                scores[specialist_id] = rating_score + efficiency_score

            return scores

        except Exception as e:
            logger.error(f"Error calculating performance scores: {str(e)}")
            return {
                specialist_id: 0.5 for specialist_id in specialist_ids
            }  # Default to neutral score

    @staticmethod
    def _get_specialist_working_hours(
        specialist_id: str, day_of_week: int
    ) -> List[Tuple[datetime.time, datetime.time]]:
        """
        Get working hours for a specialist on a specific day.

        Args:
            specialist_id: ID of the specialist
            day_of_week: Day of week (0-6, Monday-Sunday)

        Returns:
            List of (start_time, end_time) tuples
        """
        try:
            from apps.specialistsapp.models import WorkingHours

            working_hours = WorkingHours.objects.filter(
                specialist_id=specialist_id, day_of_week=day_of_week, is_working=True
            )

            return [(wh.start_time, wh.end_time) for wh in working_hours]

        except Exception as e:
            logger.error(f"Error getting specialist working hours: {str(e)}")
            return []

    @staticmethod
    def _calculate_hourly_availability(
        working_hours: List[Tuple[datetime.time, datetime.time]],
        appointments: List[Appointment],
    ) -> Dict[str, Dict[str, Any]]:
        """
        Calculate availability status for each hour of the day.

        Args:
            working_hours: List of working hour periods
            appointments: List of appointments

        Returns:
            Dict mapping hour to availability status
        """
        try:
            hourly_data = {}

            # Initialize hour slots (7am to 10pm)
            for hour in range(7, 23):
                hourly_data[str(hour)] = {
                    "is_working": False,
                    "booked_minutes": 0,
                    "available_minutes": 0,
                    "status": "closed",  # closed, available, partially_booked, fully_booked
                }

            # Process working hours
            for start, end in working_hours:
                start_hour = start.hour
                end_hour = end.hour if end.minute == 0 else end.hour + 1

                for hour in range(start_hour, end_hour):
                    if 7 <= hour < 23:  # Only process hours in our range
                        hour_key = str(hour)

                        # Calculate available minutes in this hour
                        if hour == start_hour:
                            available_from = start.minute
                        else:
                            available_from = 0

                        if hour == end.hour:
                            available_to = end.minute
                        else:
                            available_to = 60

                        available_minutes = available_to - available_from

                        hourly_data[hour_key]["is_working"] = True
                        hourly_data[hour_key]["available_minutes"] = available_minutes
                        hourly_data[hour_key]["status"] = "available"

            # Process appointments
            for appt in appointments:
                start_hour = appt.start_time.hour
                end_hour = (
                    appt.end_time.hour
                    if appt.end_time.minute == 0
                    else appt.end_time.hour + 1
                )

                for hour in range(start_hour, end_hour):
                    if 7 <= hour < 23:  # Only process hours in our range
                        hour_key = str(hour)

                        # Skip if not working during this hour
                        if not hourly_data[hour_key]["is_working"]:
                            continue

                        # Calculate booked minutes in this hour
                        if hour == start_hour:
                            booked_from = appt.start_time.minute
                        else:
                            booked_from = 0

                        if hour == appt.end_time.hour:
                            booked_to = appt.end_time.minute
                        else:
                            booked_to = 60

                        booked_minutes = booked_to - booked_from

                        hourly_data[hour_key]["booked_minutes"] += booked_minutes

            # Update status based on booking ratio
            for hour_key, data in hourly_data.items():
                if data["is_working"]:
                    available = data["available_minutes"]
                    booked = data["booked_minutes"]

                    if booked >= available:
                        data["status"] = "fully_booked"
                    elif booked > 0:
                        data["status"] = "partially_booked"

            return hourly_data

        except Exception as e:
            logger.error(f"Error calculating hourly availability: {str(e)}")
            return {}
