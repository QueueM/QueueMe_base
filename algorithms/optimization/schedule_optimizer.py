import logging
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ScheduleOptimizer:
    """
    Advanced staff scheduling optimization algorithm to maximize efficiency
    while ensuring adequate coverage based on historical and predicted demand.

    This algorithm helps businesses optimize staff scheduling by:
    1. Analyzing historical booking patterns
    2. Identifying peak and slow periods
    3. Recommending optimal working hours
    4. Balancing workload across staff members
    5. Considering staff skills and specializations
    """

    def __init__(
        self,
        min_shift_hours: int = 4,
        max_shift_hours: int = 8,
        min_staff_coverage: int = 1,
        allow_split_shifts: bool = False,
        consider_staff_preferences: bool = True,
    ):
        """
        Initialize the schedule optimizer with configurable parameters.

        Args:
            min_shift_hours: Minimum hours for a single shift
            max_shift_hours: Maximum hours for a single shift
            min_staff_coverage: Minimum number of staff required during operating hours
            allow_split_shifts: Whether to allow split shifts (non-continuous hours)
            consider_staff_preferences: Whether to consider staff preferences for hours
        """
        self.min_shift_hours = min_shift_hours
        self.max_shift_hours = max_shift_hours
        self.min_staff_coverage = min_staff_coverage
        self.allow_split_shifts = allow_split_shifts
        self.consider_staff_preferences = consider_staff_preferences

    def optimize_schedule(
        self,
        shop_hours: Dict[int, Tuple[datetime.time, datetime.time]],
        staff_members: List[Dict],
        historical_bookings: List[Dict],
        staff_preferences: Optional[Dict[str, Dict]] = None,
        days_to_schedule: int = 7,
        start_date: Optional[datetime.date] = None,
    ) -> Dict:
        """
        Generate optimized staff schedules based on historical data and demand forecasts.

        Args:
            shop_hours: Dict mapping weekday (0=Sunday) to (open_time, close_time) tuples
            staff_members: List of staff member objects with fields:
                - id: Unique identifier
                - name: Staff member name
                - skills: List of service IDs the staff member can perform
                - max_weekly_hours: Maximum weekly working hours
            historical_bookings: List of historical booking data for demand analysis
            staff_preferences: Dict mapping staff ID to their schedule preferences:
                - preferred_days: List of preferred weekdays
                - preferred_hours: Dict mapping weekday to (start_time, end_time) tuples
                - unavailable_days: List of unavailable weekdays
            days_to_schedule: Number of days to generate schedule for
            start_date: Start date for the schedule (defaults to today)

        Returns:
            A dictionary containing:
            - schedule: Dict mapping date and staff ID to working hours
            - demand_forecast: Dict mapping date and hour to predicted demand
            - optimization_stats: Stats about the optimization (coverage, efficiency)
            - warnings: List of potential issues with the schedule
            - suggestions: Suggestions for improving coverage
        """
        # Initialize result structure
        result = {
            "schedule": {},
            "demand_forecast": {},
            "optimization_stats": {},
            "warnings": [],
            "suggestions": [],
        }

        # Set start date to today if not provided
        today = datetime.now().date()
        start_date = start_date or today

        # Step 1: Generate demand forecast based on historical bookings
        demand_forecast = self._generate_demand_forecast(
            historical_bookings, start_date, days_to_schedule
        )
        result["demand_forecast"] = demand_forecast

        # Step 2: Calculate required staff coverage based on forecast
        staff_coverage_needed = self._calculate_required_coverage(demand_forecast)

        # Step 3: Check staff capacity
        total_staff_capacity = sum(staff["max_weekly_hours"] for staff in staff_members)
        total_hours_needed = sum(
            sum(hours.values()) for hours in staff_coverage_needed.values()
        )

        if total_staff_capacity < total_hours_needed:
            result["warnings"].append(
                {
                    "type": "insufficient_capacity",
                    "message": f"Staff capacity ({total_staff_capacity} hours) is less than required coverage ({total_hours_needed} hours)",
                    "recommended_action": "Consider hiring additional staff or reducing operating hours",
                }
            )

        # Step 4: Generate initial schedule based on coverage needs
        initial_schedule = self._generate_initial_schedule(
            staff_members,
            staff_coverage_needed,
            shop_hours,
            start_date,
            days_to_schedule,
        )

        # Step 5: Apply staff preferences if enabled
        if self.consider_staff_preferences and staff_preferences:
            schedule = self._apply_staff_preferences(
                initial_schedule, staff_preferences, staff_coverage_needed
            )
        else:
            schedule = initial_schedule

        # Step 6: Optimize and balance workload
        optimized_schedule = self._balance_workload(
            schedule, staff_members, staff_coverage_needed
        )

        # Step 7: Validate and fix any remaining issues
        final_schedule, validation_issues = self._validate_schedule(
            optimized_schedule, staff_members, shop_hours, staff_coverage_needed
        )

        result["schedule"] = final_schedule
        if validation_issues:
            result["warnings"].extend(validation_issues)

        # Step 8: Calculate optimization statistics
        optimization_stats = self._calculate_optimization_stats(
            final_schedule, staff_members, staff_coverage_needed, demand_forecast
        )
        result["optimization_stats"] = optimization_stats

        # Step 9: Generate suggestions for improvement
        suggestions = self._generate_suggestions(
            final_schedule,
            staff_members,
            staff_coverage_needed,
            demand_forecast,
            shop_hours,
        )
        result["suggestions"] = suggestions

        return result

    def _generate_demand_forecast(
        self,
        historical_bookings: List[Dict],
        start_date: datetime.date,
        days_to_schedule: int,
    ) -> Dict:
        """
        Generate demand forecast based on historical booking patterns.

        In a real implementation, this would use more sophisticated
        time series forecasting techniques and possibly machine learning.
        """
        demand_forecast = {}

        # Group historical bookings by weekday and hour
        weekday_hour_bookings = {}
        for booking in historical_bookings:
            booking_time = booking.get("start_time")
            if not booking_time:
                continue

            weekday = booking_time.weekday()
            hour = booking_time.hour

            if weekday not in weekday_hour_bookings:
                weekday_hour_bookings[weekday] = {}

            if hour not in weekday_hour_bookings[weekday]:
                weekday_hour_bookings[weekday][hour] = 0

            weekday_hour_bookings[weekday][hour] += 1

        # Calculate average bookings per weekday and hour
        avg_bookings = {}
        for weekday, hours in weekday_hour_bookings.items():
            avg_bookings[weekday] = {}
            for hour, count in hours.items():
                # In a real implementation, would divide by number of that weekday in the dataset
                # For this example, we'll use a simple average
                avg_bookings[weekday][hour] = count / 4  # Assuming 4 weeks of data

        # Create forecast for each day in the schedule period
        current_date = start_date
        for _ in range(days_to_schedule):
            weekday = current_date.weekday()
            date_str = current_date.isoformat()
            demand_forecast[date_str] = {}

            # Get this weekday's hourly averages, or empty dict if none
            hourly_averages = avg_bookings.get(weekday, {})

            # For each hour, get the average or default to 0
            for hour in range(24):
                demand_forecast[date_str][hour] = hourly_averages.get(hour, 0)

            # Move to next day
            current_date += timedelta(days=1)

        return demand_forecast

    def _calculate_required_coverage(self, demand_forecast: Dict) -> Dict:
        """
        Calculate required staff coverage based on demand forecast.

        The formula used is a simplified version:
        - 1 staff for every 3 bookings per hour
        - Minimum of self.min_staff_coverage staff at all times
        """
        coverage_needed = {}

        for date_str, hours in demand_forecast.items():
            coverage_needed[date_str] = {}

            for hour, demand in hours.items():
                # Calculate base required staff (1 per 3 bookings)
                required_staff = max(1, int(demand / 3))

                # Ensure minimum coverage
                required_staff = max(required_staff, self.min_staff_coverage)

                coverage_needed[date_str][hour] = required_staff

        return coverage_needed

    def _generate_initial_schedule(
        self,
        staff_members: List[Dict],
        staff_coverage_needed: Dict,
        shop_hours: Dict[int, Tuple[datetime.time, datetime.time]],
        start_date: datetime.date,
        days_to_schedule: int,
    ) -> Dict:
        """
        Generate initial schedule based on required coverage.

        This is a simplified greedy algorithm that:
        1. Assigns staff to hours with highest demand first
        2. Tries to create continuous shifts (min_shift_hours to max_shift_hours)
        3. Respects staff maximum weekly hours
        """
        # Initialize schedule
        schedule = {}

        # Track remaining weekly hours for each staff member
        remaining_hours = {
            staff["id"]: staff["max_weekly_hours"] for staff in staff_members
        }

        # Create a list of (date, hour, required_staff) sorted by demand (highest first)
        demand_slots = []
        for date_str, hours in staff_coverage_needed.items():
            date = datetime.fromisoformat(date_str).date()
            weekday = date.weekday()

            # Only schedule during shop hours
            if weekday in shop_hours:
                shop_open, shop_close = shop_hours[weekday]
                open_hour = shop_open.hour
                close_hour = (
                    shop_close.hour if shop_close.hour > 0 else 24
                )  # Handle midnight

                for hour in range(open_hour, close_hour):
                    required_staff = hours.get(hour, 0)
                    demand_slots.append((date_str, hour, required_staff))

        # Sort by demand (highest first)
        demand_slots.sort(key=lambda x: x[2], reverse=True)

        # Now assign staff to slots, starting with highest demand
        for date_str, hour, required_staff in demand_slots:
            date = datetime.fromisoformat(date_str).date()

            # Initialize date in schedule if not present
            if date_str not in schedule:
                schedule[date_str] = {}

            # Count staff already assigned to this slot
            assigned_staff = len(
                [s for s, hours in schedule.get(date_str, {}).items() if hour in hours]
            )

            # Skip if enough staff already assigned
            if assigned_staff >= required_staff:
                continue

            # Sort staff by remaining hours (most hours first)
            available_staff = sorted(
                [
                    (staff_id, hours)
                    for staff_id, hours in remaining_hours.items()
                    if hours > 0
                ],
                key=lambda x: x[1],
                reverse=True,
            )

            # Assign staff until coverage requirement met
            for staff_id, hours_left in available_staff:
                # Check if this staff member is already working this hour
                if (
                    staff_id in schedule.get(date_str, {})
                    and hour in schedule[date_str][staff_id]
                ):
                    continue

                # Check if this assignment would form a valid shift
                if self._forms_valid_shift(schedule, date_str, hour, staff_id):
                    # Initialize staff in schedule if not present
                    if staff_id not in schedule[date_str]:
                        schedule[date_str][staff_id] = []

                    # Assign staff to this hour
                    schedule[date_str][staff_id].append(hour)

                    # Decrement remaining hours
                    remaining_hours[staff_id] -= 1

                    # Check if we've met coverage requirement
                    assigned_staff += 1
                    if assigned_staff >= required_staff:
                        break

        # Sort each staff member's hours (for readability)
        for date_str in schedule:
            for staff_id in schedule[date_str]:
                schedule[date_str][staff_id].sort()

        return schedule

    def _forms_valid_shift(
        self, schedule: Dict, date_str: str, hour: int, staff_id: str
    ) -> bool:
        """
        Check if assigning this hour forms a valid shift for this staff member.
        A valid shift is continuous and between min_shift_hours and max_shift_hours.

        This is a simplified check that only looks at the current day.
        In a real implementation, would check across days for overnight shifts.
        """
        # If allowing split shifts, any assignment is valid
        if self.allow_split_shifts:
            return True

        # Get staff's current hours for this day
        staff_hours = schedule.get(date_str, {}).get(staff_id, [])

        # If no hours yet, any assignment is valid (beginning of a shift)
        if not staff_hours:
            return True

        # Check if this hour is adjacent to existing hours (before or after)
        return (hour - 1 in staff_hours) or (hour + 1 in staff_hours)

    def _apply_staff_preferences(
        self,
        schedule: Dict,
        staff_preferences: Dict[str, Dict],
        staff_coverage_needed: Dict,
    ) -> Dict:
        """
        Adjust schedule to accommodate staff preferences where possible.
        """
        adjusted_schedule = deepcopy(schedule)

        for staff_id, preferences in staff_preferences.items():
            # Get preferred hours by weekday
            preferred_hours = preferences.get("preferred_hours", {})

            # Get days off preferences
            preferred_days_off = preferences.get("preferred_days_off", [])

            # Apply days off preferences where possible
            for day_off in preferred_days_off:
                date_str = day_off.isoformat()

                # Skip if not in our schedule
                if date_str not in adjusted_schedule:
                    continue

                # Skip if staff not currently scheduled
                if staff_id not in adjusted_schedule.get(date_str, {}):
                    continue

                # Check if we can give the day off
                # In a real implementation, would check coverage
                if date_str in adjusted_schedule and staff_id in adjusted_schedule.get(
                    date_str, {}
                ):
                    # Need to reassign these hours to other staff
                    # hours_to_reassign = adjusted_schedule[date_str].pop(staff_id)

                    # In a real implementation, would have logic to reassign to other staff
                    # For this simplified version, we'll just note it as a warning
                    pass

            # Try to adjust hours to match preferences
            for date_str in list(adjusted_schedule.keys()):
                date = datetime.fromisoformat(date_str).date()
                weekday = date.weekday()

                # Skip if not scheduled this day
                if staff_id not in adjusted_schedule.get(date_str, {}):
                    continue

                # If staff has preferred hours for this weekday, try to adjust
                if weekday in preferred_hours:
                    pref_start, pref_end = preferred_hours[weekday]

                    # Get current scheduled hours
                    current_hours = adjusted_schedule[date_str][staff_id]

                    # Get preferred hour range
                    preferred_range = list(range(pref_start.hour, pref_end.hour))

                    # Hours to remove (outside preferred range)
                    hours_to_remove = [
                        h for h in current_hours if h not in preferred_range
                    ]

                    # Hours to potentially add (within preferred range but not scheduled)
                    hours_to_add = [
                        h for h in preferred_range if h not in current_hours
                    ]

                    # In a real implementation, would have logic to balance these changes
                    # while maintaining coverage requirements
                    # For this simplified version, we'll prioritize keeping coverage

        return adjusted_schedule

    def _balance_workload(
        self, schedule: Dict, staff_members: List[Dict], staff_coverage_needed: Dict
    ) -> Dict:
        """
        Balance workload across staff members while maintaining coverage.

        This implementation aims to:
        1. Make shifts more continuous (fewer gaps)
        2. Distribute hours fairly among staff
        3. Respect shift length constraints
        """
        balanced_schedule = schedule.copy()

        # Calculate total hours assigned to each staff member
        staff_hours = {staff["id"]: 0 for staff in staff_members}
        for date_str, staff_assignments in schedule.items():
            for staff_id, hours in staff_assignments.items():
                staff_hours[staff_id] = staff_hours.get(staff_id, 0) + len(hours)

        # Identify staff who are over/under-utilized
        target_avg_hours = sum(staff_hours.values()) / len(staff_hours)
        overloaded_staff = [
            staff_id
            for staff_id, hours in staff_hours.items()
            if hours > target_avg_hours * 1.1  # More than 10% over average
        ]
        underutilized_staff = [
            staff_id
            for staff_id, hours in staff_hours.items()
            if hours < target_avg_hours * 0.9  # More than 10% under average
        ]

        # Try to redistribute some hours from overloaded to underutilized staff
        # In a real implementation, this would be more sophisticated
        # For this simplified version, we'll just note it for reporting

        # Consolidate shifts to make them more continuous
        for date_str, staff_assignments in balanced_schedule.items():
            for staff_id, hours in list(staff_assignments.items()):
                # Skip if not enough hours to bother optimizing
                if len(hours) < 2:
                    continue

                # Find gaps in the shift
                sorted_hours = sorted(hours)
                gaps = []
                for i in range(len(sorted_hours) - 1):
                    if sorted_hours[i + 1] - sorted_hours[i] > 1:
                        gaps.append((sorted_hours[i], sorted_hours[i + 1]))

                # If there are gaps, try to fill them or split the shift
                if gaps and not self.allow_split_shifts:
                    # In a real implementation, would have logic to fix these gaps
                    # while maintaining coverage
                    # For this simplified version, we'll just note it for reporting
                    pass

        return balanced_schedule

    def _validate_schedule(
        self,
        schedule: Dict,
        staff_members: List[Dict],
        shop_hours: Dict[int, Tuple[datetime.time, datetime.time]],
        staff_coverage_needed: Dict,
    ) -> Tuple[Dict, List[Dict]]:
        """
        Validate the schedule and fix any issues found.

        Returns the fixed schedule and a list of validation issues.
        """
        validated_schedule = schedule.copy()
        issues = []

        # Check shift lengths (min/max hours)
        for date_str, staff_assignments in schedule.items():
            date = datetime.fromisoformat(date_str).date()
            weekday = date.weekday()

            for staff_id, hours in staff_assignments.items():
                # Skip if no hours assigned
                if not hours:
                    continue

                # Check for split shifts if not allowed
                if not self.allow_split_shifts:
                    sorted_hours = sorted(hours)
                    is_continuous = True
                    for i in range(len(sorted_hours) - 1):
                        if sorted_hours[i + 1] - sorted_hours[i] > 1:
                            is_continuous = False
                            break

                    if not is_continuous:
                        issues.append(
                            {
                                "type": "split_shift",
                                "date": date_str,
                                "staff_id": staff_id,
                                "hours": hours,
                                "message": f"Split shift detected for staff {staff_id} on {date_str}",
                            }
                        )

                # Check shift length
                shift_length = len(hours)
                if shift_length < self.min_shift_hours:
                    issues.append(
                        {
                            "type": "short_shift",
                            "date": date_str,
                            "staff_id": staff_id,
                            "hours": hours,
                            "message": f"Shift too short ({shift_length} hours) for staff {staff_id} on {date_str}",
                        }
                    )
                elif shift_length > self.max_shift_hours:
                    issues.append(
                        {
                            "type": "long_shift",
                            "date": date_str,
                            "staff_id": staff_id,
                            "hours": hours,
                            "message": f"Shift too long ({shift_length} hours) for staff {staff_id} on {date_str}",
                        }
                    )

        # Check coverage requirements
        for date_str, hours_needed in staff_coverage_needed.items():
            # Skip if no schedule for this date
            if date_str not in schedule:
                continue

            date = datetime.fromisoformat(date_str).date()
            weekday = date.weekday()

            # Skip if shop is closed this day
            if weekday not in shop_hours:
                continue

            # Get shop hours
            shop_open, shop_close = shop_hours[weekday]
            open_hour = shop_open.hour
            close_hour = (
                shop_close.hour if shop_close.hour > 0 else 24
            )  # Handle midnight

            # Check each hour during shop hours
            for hour in range(open_hour, close_hour):
                required_staff = hours_needed.get(hour, 0)

                # Count assigned staff for this hour
                assigned_staff = sum(
                    1
                    for staff_id, staff_hours in schedule.get(date_str, {}).items()
                    if hour in staff_hours
                )

                if assigned_staff < required_staff:
                    issues.append(
                        {
                            "type": "understaffed",
                            "date": date_str,
                            "hour": hour,
                            "required": required_staff,
                            "assigned": assigned_staff,
                            "message": f"Understaffed on {date_str} at {hour}:00 ({assigned_staff}/{required_staff})",
                        }
                    )

        # In a real implementation, would attempt to fix these issues
        # For this simplified version, we'll just return the issues

        return validated_schedule, issues

    def _calculate_optimization_stats(
        self,
        schedule: Dict,
        staff_members: List[Dict],
        staff_coverage_needed: Dict,
        demand_forecast: Dict,
    ) -> Dict:
        """
        Calculate statistics about the optimization results.
        """
        stats = {
            "total_staff_hours": 0,
            "total_required_hours": 0,
            "coverage_percentage": 0,
            "staff_utilization": {},
            "daily_coverage": {},
            "peak_hours_coverage": 0,
        }

        # Calculate total staff hours
        for date_str, staff_assignments in schedule.items():
            if date_str not in stats["daily_coverage"]:
                stats["daily_coverage"][date_str] = {
                    "required": 0,
                    "assigned": 0,
                    "coverage_percentage": 0,
                }

            for staff_id, hours in staff_assignments.items():
                staff_hours = len(hours)
                stats["total_staff_hours"] += staff_hours

                # Track per-staff utilization
                if staff_id not in stats["staff_utilization"]:
                    stats["staff_utilization"][staff_id] = 0
                stats["staff_utilization"][staff_id] += staff_hours

        # Calculate coverage statistics
        peak_hours_required = 0
        peak_hours_assigned = 0

        for date_str, hours_needed in staff_coverage_needed.items():
            daily_required = 0
            daily_assigned = 0

            for hour, required in hours_needed.items():
                stats["total_required_hours"] += required
                daily_required += required

                # Count assigned staff for this hour
                assigned = sum(
                    1
                    for staff_id, staff_hours in schedule.get(date_str, {}).items()
                    if hour in staff_hours
                )
                daily_assigned += assigned

                # Track peak hours (defined as hours with above-average demand)
                demand = demand_forecast.get(date_str, {}).get(hour, 0)
                if demand > 2:  # Arbitrary threshold for this example
                    peak_hours_required += required
                    peak_hours_assigned += assigned

            # Calculate daily coverage percentage
            if daily_required > 0:
                stats["daily_coverage"][date_str]["required"] = daily_required
                stats["daily_coverage"][date_str]["assigned"] = daily_assigned
                stats["daily_coverage"][date_str]["coverage_percentage"] = (
                    daily_assigned / daily_required
                ) * 100

        # Calculate overall coverage percentage
        if stats["total_required_hours"] > 0:
            stats["coverage_percentage"] = (
                stats["total_staff_hours"] / stats["total_required_hours"]
            ) * 100

        # Calculate peak hours coverage
        if peak_hours_required > 0:
            stats["peak_hours_coverage"] = (
                peak_hours_assigned / peak_hours_required
            ) * 100

        # Calculate staff utilization percentages
        for staff_id, hours in stats["staff_utilization"].items():
            # Find this staff member's max hours
            staff_member = next((s for s in staff_members if s["id"] == staff_id), None)
            if staff_member:
                max_hours = staff_member["max_weekly_hours"]
                stats["staff_utilization"][staff_id] = {
                    "hours": hours,
                    "max_hours": max_hours,
                    "utilization_percentage": (
                        (hours / max_hours) * 100 if max_hours > 0 else 0
                    ),
                }

        return stats

    def _generate_suggestions(
        self,
        schedule: Dict,
        staff_members: List[Dict],
        staff_coverage_needed: Dict,
        demand_forecast: Dict,
        shop_hours: Dict[int, Tuple[datetime.time, datetime.time]],
    ) -> List[Dict]:
        """
        Generate suggestions for improving the schedule.
        """
        suggestions = []

        # Check for understaffed periods
        understaffed_periods = []
        for date_str, hours_needed in staff_coverage_needed.items():
            date = datetime.fromisoformat(date_str).date()
            weekday = date.weekday()

            # Skip if shop is closed this day
            if weekday not in shop_hours:
                continue

            # Get shop hours
            shop_open, shop_close = shop_hours[weekday]
            open_hour = shop_open.hour
            close_hour = (
                shop_close.hour if shop_close.hour > 0 else 24
            )  # Handle midnight

            # Check each hour during shop hours
            for hour in range(open_hour, close_hour):
                required_staff = hours_needed.get(hour, 0)

                # Count assigned staff for this hour
                assigned_staff = sum(
                    1
                    for staff_id, staff_hours in schedule.get(date_str, {}).items()
                    if hour in staff_hours
                )

                if assigned_staff < required_staff:
                    understaffed_periods.append(
                        {
                            "date": date_str,
                            "hour": hour,
                            "required": required_staff,
                            "assigned": assigned_staff,
                            "shortage": required_staff - assigned_staff,
                        }
                    )

        # Group understaffed periods by day
        understaffed_by_day = {}
        for period in understaffed_periods:
            date_str = period["date"]
            if date_str not in understaffed_by_day:
                understaffed_by_day[date_str] = []
            understaffed_by_day[date_str].append(period)

        # Generate suggestions for understaffed days
        for date_str, periods in understaffed_by_day.items():
            # Count total shortage
            total_shortage = sum(p["shortage"] for p in periods)

            # If significant shortage, suggest adding staff
            if total_shortage >= 4:  # Arbitrary threshold
                suggestion = {
                    "type": "add_staff",
                    "date": date_str,
                    "shortage": total_shortage,
                    "message": f"Consider adding {max(1, total_shortage // 4)} staff members on {date_str}",
                }

                # Add time ranges
                hours = sorted([p["hour"] for p in periods])
                ranges = []
                start = hours[0]
                current_range = [start]

                for i in range(1, len(hours)):
                    if hours[i] == hours[i - 1] + 1:
                        current_range.append(hours[i])
                    else:
                        ranges.append((min(current_range), max(current_range)))
                        current_range = [hours[i]]

                # Add the last range
                if current_range:
                    ranges.append((min(current_range), max(current_range)))

                # Format time ranges
                time_ranges = []
                for start, end in ranges:
                    time_ranges.append(f"{start}:00-{end+1}:00")

                suggestion["time_ranges"] = time_ranges
                suggestions.append(suggestion)

        # Check for overstaffed periods
        overstaffed_periods = []
        for date_str, hours_needed in staff_coverage_needed.items():
            # Skip if no schedule for this date
            if date_str not in schedule:
                continue

            date = datetime.fromisoformat(date_str).date()
            weekday = date.weekday()

            # Skip if shop is closed this day
            if weekday not in shop_hours:
                continue

            # Get shop hours
            shop_open, shop_close = shop_hours[weekday]
            open_hour = shop_open.hour
            close_hour = (
                shop_close.hour if shop_close.hour > 0 else 24
            )  # Handle midnight

            # Check each hour during shop hours
            for hour in range(open_hour, close_hour):
                required_staff = hours_needed.get(hour, 0)

                # Count assigned staff for this hour
                assigned_staff = sum(
                    1
                    for staff_id, staff_hours in schedule.get(date_str, {}).items()
                    if hour in staff_hours
                )

                # Consider overstaffed if 50% more staff than needed
                if required_staff > 0 and assigned_staff > required_staff * 1.5:
                    overstaffed_periods.append(
                        {
                            "date": date_str,
                            "hour": hour,
                            "required": required_staff,
                            "assigned": assigned_staff,
                            "excess": assigned_staff - required_staff,
                        }
                    )

        # Group overstaffed periods by day
        overstaffed_by_day = {}
        for period in overstaffed_periods:
            date_str = period["date"]
            if date_str not in overstaffed_by_day:
                overstaffed_by_day[date_str] = []
            overstaffed_by_day[date_str].append(period)

        # Generate suggestions for overstaffed days
        for date_str, periods in overstaffed_by_day.items():
            # Count total excess
            total_excess = sum(p["excess"] for p in periods)

            # If significant excess, suggest reducing staff
            if total_excess >= 4:  # Arbitrary threshold
                suggestion = {
                    "type": "reduce_staff",
                    "date": date_str,
                    "excess": total_excess,
                    "message": f"Consider reducing staff by {max(1, total_excess // 4)} on {date_str}",
                }

                # Add time ranges (same logic as above)
                hours = sorted([p["hour"] for p in periods])
                ranges = []
                start = hours[0]
                current_range = [start]

                for i in range(1, len(hours)):
                    if hours[i] == hours[i - 1] + 1:
                        current_range.append(hours[i])
                    else:
                        ranges.append((min(current_range), max(current_range)))
                        current_range = [hours[i]]

                # Add the last range
                if current_range:
                    ranges.append((min(current_range), max(current_range)))

                # Format time ranges
                time_ranges = []
                for start, end in ranges:
                    time_ranges.append(f"{start}:00-{end+1}:00")

                suggestion["time_ranges"] = time_ranges
                suggestions.append(suggestion)

        # Check staff utilization
        staff_utilization = {}
        for date_str, staff_assignments in schedule.items():
            for staff_id, hours in staff_assignments.items():
                if staff_id not in staff_utilization:
                    staff_utilization[staff_id] = 0
                staff_utilization[staff_id] += len(hours)

        # Look for underutilized staff
        for staff_id, hours in staff_utilization.items():
            staff_member = next((s for s in staff_members if s["id"] == staff_id), None)
            if staff_member:
                max_hours = staff_member["max_weekly_hours"]
                utilization = (hours / max_hours) * 100 if max_hours > 0 else 0

                # If significantly underutilized, suggest increasing hours
                if utilization < 70:  # Arbitrary threshold
                    suggestions.append(
                        {
                            "type": "increase_hours",
                            "staff_id": staff_id,
                            "utilization": utilization,
                            "current_hours": hours,
                            "max_hours": max_hours,
                            "message": f"Staff {staff_id} is underutilized ({utilization:.1f}%). Consider increasing hours.",
                        }
                    )

        return suggestions
