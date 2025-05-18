import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class WorkloadBalancer:
    """
    Specialist workload balancing algorithm that evenly distributes
    appointments across specialists based on skills, availability, and preferences.

    This algorithm helps businesses optimize specialist assignment by:
    1. Ensuring fair distribution of work
    2. Considering specialist skills and specializations
    3. Respecting working hours and preferences
    4. Maximizing efficiency and customer satisfaction
    5. Preventing specialist burnout
    """

    def __init__(
        self,
        consider_specialist_ratings: bool = True,
        consider_service_complexity: bool = True,
        respect_customer_preferences: bool = True,
        max_daily_bookings_per_specialist: Optional[int] = None,
        balance_window_days: int = 7,
    ):
        """
        Initialize the workload balancer with configurable parameters.

        Args:
            consider_specialist_ratings: Whether to consider ratings in assignment
            consider_service_complexity: Whether to factor in service complexity
            respect_customer_preferences: Whether to respect customer preferences for specialists
            max_daily_bookings_per_specialist: Maximum bookings per day per specialist (None = unlimited)
            balance_window_days: Number of days to consider for balancing work
        """
        self.consider_specialist_ratings = consider_specialist_ratings
        self.consider_service_complexity = consider_service_complexity
        self.respect_customer_preferences = respect_customer_preferences
        self.max_daily_bookings_per_specialist = max_daily_bookings_per_specialist
        self.balance_window_days = balance_window_days

    def balance_workload(
        self,
        specialists: List[Dict],
        services: List[Dict],
        appointments: List[Dict],
        specialist_services: List[Dict],
        customer_preferences: Optional[Dict] = None,
        start_date: Optional[datetime.date] = None,
        end_date: Optional[datetime.date] = None,
    ) -> Dict:
        """
        Balance workload across specialists for a given time period.

        Args:
            specialists: List of specialist objects with fields:
                - id: Unique identifier
                - employee_id: ID of the employee record
                - ratings: Average rating score
                - experience_years: Years of experience
            services: List of service objects with fields:
                - id: Unique identifier
                - name: Service name
                - duration: Service duration in minutes
                - complexity: Optional complexity rating (1-5)
            appointments: List of appointment objects with fields:
                - id: Unique identifier
                - service_id: ID of the service
                - specialist_id: ID of assigned specialist (may be None for reassignment)
                - customer_id: ID of the customer
                - start_time: Start datetime
                - end_time: End datetime
                - status: Status of the appointment
            specialist_services: List of mappings between specialists and services with fields:
                - specialist_id: ID of the specialist
                - service_id: ID of the service
                - is_primary: Whether this is a primary service for the specialist
            customer_preferences: Dict mapping customer ID to preferred specialist IDs
            start_date: Start date for balancing (defaults to today)
            end_date: End date for balancing (defaults to start_date + balance_window_days)

        Returns:
            A dictionary containing:
            - balanced_appointments: List of appointments with updated specialist assignments
            - workload_stats: Statistics about the workload distribution
            - specialist_utilization: Data about each specialist's utilization
            - recommendations: Additional recommendations for further optimization
        """
        # Initialize result structure
        result = {
            "balanced_appointments": [],
            "workload_stats": {},
            "specialist_utilization": {},
            "recommendations": [],
        }

        # Set default dates if not provided
        today = datetime.now().date()
        start_date = start_date or today
        end_date = end_date or (start_date + timedelta(days=self.balance_window_days))

        # Step 1: Analyze current workload distribution
        current_workload = self._analyze_current_workload(
            specialists, appointments, services, start_date, end_date
        )

        # Step 2: Create mappings for faster lookups
        service_map = {service["id"]: service for service in services}
        specialist_map = {specialist["id"]: specialist for specialist in specialists}

        # Create service-to-specialists mapping
        service_specialists = {}
        for mapping in specialist_services:
            service_id = mapping["service_id"]
            specialist_id = mapping["specialist_id"]
            is_primary = mapping.get("is_primary", False)

            if service_id not in service_specialists:
                service_specialists[service_id] = []

            service_specialists[service_id].append(
                {"specialist_id": specialist_id, "is_primary": is_primary}
            )

        # Step 3: Identify appointments eligible for reassignment
        reassignable_appointments = []
        fixed_appointments = []

        for appointment in appointments:
            # Skip appointments outside the date range
            appointment_date = appointment["start_time"].date()
            if appointment_date < start_date or appointment_date > end_date:
                continue

            # Skip completed or canceled appointments
            if appointment["status"] in ["completed", "cancelled", "no_show"]:
                continue

            # If appointment has no specialist assigned, it's eligible for assignment
            if appointment.get("specialist_id") is None:
                reassignable_appointments.append(appointment)
                continue

            # Check if this appointment should be fixed (customer requested specific specialist)
            customer_id = appointment["customer_id"]
            current_specialist_id = appointment["specialist_id"]

            is_customer_preference = False
            if customer_preferences and customer_id in customer_preferences:
                preferred_specialists = customer_preferences[customer_id]
                if current_specialist_id in preferred_specialists:
                    is_customer_preference = True

            # If it's a customer preference and we respect those, keep the assignment
            if is_customer_preference and self.respect_customer_preferences:
                fixed_appointments.append(appointment)
            else:
                # Otherwise, it's eligible for reassignment
                reassignable_appointments.append(appointment)

        # Step 4: Calculate target workload per specialist
        total_appointments = len(fixed_appointments) + len(reassignable_appointments)
        target_per_specialist = total_appointments / len(specialists) if specialists else 0

        # Track current workload accounting for fixed appointments
        current_specialist_count = {specialist["id"]: 0 for specialist in specialists}
        for appointment in fixed_appointments:
            specialist_id = appointment["specialist_id"]
            if specialist_id in current_specialist_count:
                current_specialist_count[specialist_id] += 1

        # Step 5: Balance workload by reassigning specialists
        balanced_appointments = fixed_appointments.copy()

        # Process reassignable appointments
        for appointment in reassignable_appointments:
            service_id = appointment["service_id"]
            appointment_time = appointment["start_time"]

            # Get specialists who can provide this service
            eligible_specialists = service_specialists.get(service_id, [])
            if not eligible_specialists:
                # No eligible specialists, leave as unassigned
                balanced_appointments.append(appointment)
                result["recommendations"].append(
                    {
                        "type": "unassigned_service",
                        "appointment_id": appointment["id"],
                        "service_id": service_id,
                        "message": f"No specialists available for service {service_id}",
                    }
                )
                continue

            # Find specialists available at this time
            available_specialists = self._find_available_specialists(
                eligible_specialists, appointment, balanced_appointments, specialist_map
            )

            if not available_specialists:
                # No available specialists, leave as unassigned
                balanced_appointments.append(appointment)
                result["recommendations"].append(
                    {
                        "type": "scheduling_conflict",
                        "appointment_id": appointment["id"],
                        "service_id": service_id,
                        "appointment_time": appointment_time,
                        "message": f"No specialists available at {appointment_time} for service {service_id}",
                    }
                )
                continue

            # Score specialists based on balancing criteria
            scored_specialists = []

            for specialist_info in available_specialists:
                specialist_id = specialist_info["specialist_id"]
                specialist = specialist_map[specialist_id]
                is_primary = specialist_info["is_primary"]

                # Calculate base score (lower workload = higher score)
                workload = current_specialist_count.get(specialist_id, 0)
                base_score = target_per_specialist - workload

                # Adjust score based on various factors
                score = base_score

                # Primary service specialist bonus
                if is_primary:
                    score += 1.0

                # Rating bonus if enabled
                if self.consider_specialist_ratings and "ratings" in specialist:
                    rating = specialist["ratings"]
                    # Normalize rating to a small bonus (0-0.5)
                    rating_bonus = (rating - 3) / 4 if rating > 3 else 0
                    score += rating_bonus

                # Service complexity consideration if enabled
                if self.consider_service_complexity:
                    service = service_map.get(service_id, {})
                    complexity = service.get("complexity", 3)  # Default to medium

                    # Experience adjustment based on complexity
                    experience_years = specialist.get("experience_years", 1)

                    # For complex services, favor experienced specialists
                    if complexity >= 4 and experience_years > 3:
                        score += 0.5
                    # For simple services, spread to all specialists
                    elif complexity <= 2:
                        score += 0.2

                # Customer preference bonus
                customer_id = appointment["customer_id"]
                if (
                    self.respect_customer_preferences
                    and customer_preferences
                    and customer_id in customer_preferences
                ):
                    preferred_specialists = customer_preferences[customer_id]
                    if specialist_id in preferred_specialists:
                        score += 2.0  # Strong bonus for customer preference

                scored_specialists.append({"specialist_id": specialist_id, "score": score})

            # Find the specialist with the highest score
            best_specialist = max(scored_specialists, key=lambda x: x["score"])
            best_specialist_id = best_specialist["specialist_id"]

            # Assign the specialist
            updated_appointment = appointment.copy()
            updated_appointment["specialist_id"] = best_specialist_id
            balanced_appointments.append(updated_appointment)

            # Update workload count
            current_specialist_count[best_specialist_id] = (
                current_specialist_count.get(best_specialist_id, 0) + 1
            )

        # Step 6: Calculate final workload statistics
        specialist_appointment_counts = {specialist["id"]: 0 for specialist in specialists}
        specialist_service_minutes = {specialist["id"]: 0 for specialist in specialists}

        for appointment in balanced_appointments:
            specialist_id = appointment.get("specialist_id")
            if specialist_id in specialist_appointment_counts:
                specialist_appointment_counts[specialist_id] += 1

                # Calculate service duration
                service_id = appointment["service_id"]
                service = service_map.get(service_id, {})
                duration = service.get("duration", 30)  # Default to 30 minutes

                specialist_service_minutes[specialist_id] += duration

        # Calculate workload stats
        workload_stats = {
            "total_appointments": len(balanced_appointments),
            "assigned_appointments": sum(
                1 for a in balanced_appointments if a.get("specialist_id")
            ),
            "unassigned_appointments": sum(
                1 for a in balanced_appointments if not a.get("specialist_id")
            ),
            "min_appointments": (
                min(specialist_appointment_counts.values()) if specialist_appointment_counts else 0
            ),
            "max_appointments": (
                max(specialist_appointment_counts.values()) if specialist_appointment_counts else 0
            ),
            "avg_appointments": (
                sum(specialist_appointment_counts.values()) / len(specialists) if specialists else 0
            ),
        }

        # Calculate standard deviation (measure of balance)
        if specialists:
            values = list(specialist_appointment_counts.values())
            mean = sum(values) / len(values)
            variance = sum((x - mean) ** 2 for x in values) / len(values)
            std_dev = variance**0.5
            workload_stats["appointment_std_dev"] = std_dev

            # Interpret the balance level
            if std_dev < 1:
                workload_stats["balance_level"] = "excellent"
            elif std_dev < 2:
                workload_stats["balance_level"] = "good"
            elif std_dev < 3:
                workload_stats["balance_level"] = "moderate"
            else:
                workload_stats["balance_level"] = "poor"

        # Prepare specialist utilization data
        specialist_utilization = {}
        for specialist in specialists:
            specialist_id = specialist["id"]
            appointment_count = specialist_appointment_counts.get(specialist_id, 0)
            service_minutes = specialist_service_minutes.get(specialist_id, 0)

            specialist_utilization[specialist_id] = {
                "appointment_count": appointment_count,
                "service_minutes": service_minutes,
                "percent_of_total": (
                    (appointment_count / workload_stats["total_appointments"]) * 100
                    if workload_stats["total_appointments"] > 0
                    else 0
                ),
            }

        # Generate additional recommendations
        recommendations = []

        # Check for specialists with too few appointments
        for specialist_id, count in specialist_appointment_counts.items():
            if count < workload_stats["avg_appointments"] * 0.5 and count < 3:
                recommendations.append(
                    {
                        "type": "underutilized_specialist",
                        "specialist_id": specialist_id,
                        "appointment_count": count,
                        "message": f"Specialist {specialist_id} is significantly underutilized with only {count} appointments",
                    }
                )

        # Check for specialists with too many appointments
        for specialist_id, count in specialist_appointment_counts.items():
            if count > workload_stats["avg_appointments"] * 1.5 and count > 5:
                recommendations.append(
                    {
                        "type": "overloaded_specialist",
                        "specialist_id": specialist_id,
                        "appointment_count": count,
                        "message": f"Specialist {specialist_id} is potentially overloaded with {count} appointments",
                    }
                )

        # Populate result
        result["balanced_appointments"] = balanced_appointments
        result["workload_stats"] = workload_stats
        result["specialist_utilization"] = specialist_utilization
        result["recommendations"].extend(recommendations)

        return result

    def _analyze_current_workload(
        self,
        specialists: List[Dict],
        appointments: List[Dict],
        services: List[Dict],
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> Dict:
        """
        Analyze the current workload distribution among specialists.
        """
        # Create service map for lookup
        service_map = {service["id"]: service for service in services}

        # Initialize workload counters
        appointment_counts = {specialist["id"]: 0 for specialist in specialists}
        service_minutes = {specialist["id"]: 0 for specialist in specialists}

        # Count appointments per specialist
        for appointment in appointments:
            specialist_id = appointment.get("specialist_id")
            if not specialist_id:
                continue

            # Skip appointments outside the date range
            appointment_date = appointment["start_time"].date()
            if appointment_date < start_date or appointment_date > end_date:
                continue

            # Skip completed or canceled appointments
            if appointment["status"] in ["completed", "cancelled", "no_show"]:
                continue

            # Increment appointment count
            appointment_counts[specialist_id] = appointment_counts.get(specialist_id, 0) + 1

            # Add service duration
            service_id = appointment["service_id"]
            service = service_map.get(service_id, {})
            duration = service.get("duration", 30)  # Default to 30 minutes

            service_minutes[specialist_id] = service_minutes.get(specialist_id, 0) + duration

        # Group appointments by day for each specialist
        daily_counts = {}
        for appointment in appointments:
            specialist_id = appointment.get("specialist_id")
            if not specialist_id:
                continue

            # Skip completed or canceled appointments
            if appointment["status"] in ["completed", "cancelled", "no_show"]:
                continue

            # Get the date
            appointment_date = appointment["start_time"].date()
            if appointment_date < start_date or appointment_date > end_date:
                continue

            date_str = appointment_date.isoformat()

            if specialist_id not in daily_counts:
                daily_counts[specialist_id] = {}

            if date_str not in daily_counts[specialist_id]:
                daily_counts[specialist_id][date_str] = 0

            daily_counts[specialist_id][date_str] += 1

        # Find days exceeding maximum bookings (if configured)
        days_exceeding_max = []
        if self.max_daily_bookings_per_specialist:
            for specialist_id, dates in daily_counts.items():
                for date_str, count in dates.items():
                    if count > self.max_daily_bookings_per_specialist:
                        days_exceeding_max.append(
                            {
                                "specialist_id": specialist_id,
                                "date": date_str,
                                "count": count,
                                "max": self.max_daily_bookings_per_specialist,
                            }
                        )

        return {
            "appointment_counts": appointment_counts,
            "service_minutes": service_minutes,
            "daily_counts": daily_counts,
            "days_exceeding_max": days_exceeding_max,
        }

    def _find_available_specialists(
        self,
        eligible_specialists: List[Dict],
        appointment: Dict,
        existing_appointments: List[Dict],
        specialist_map: Dict[str, Dict],
    ) -> List[Dict]:
        """
        Find specialists available for a specific appointment time.
        """
        start_time = appointment["start_time"]
        end_time = appointment["end_time"]
        appointment_id = appointment["id"]

        available_specialists = []

        for specialist_info in eligible_specialists:
            specialist_id = specialist_info["specialist_id"]

            # Check if specialist exists in the map
            if specialist_id not in specialist_map:
                continue

            # Check if specialist is already booked during this time
            is_available = True
            for existing in existing_appointments:
                # Skip self-comparison
                if existing["id"] == appointment_id:
                    continue

                # Skip if not assigned to this specialist
                if existing.get("specialist_id") != specialist_id:
                    continue

                # Check for time overlap
                existing_start = existing["start_time"]
                existing_end = existing["end_time"]

                if start_time < existing_end and end_time > existing_start:
                    is_available = False
                    break

            if is_available:
                available_specialists.append(specialist_info)

        return available_specialists
