"""
Constraint satisfaction solver for scheduling problems.

This module provides a sophisticated constraint satisfaction algorithm to solve
complex scheduling problems with multiple constraints, such as booking multiple
services while respecting dependencies, resource availability, and time constraints.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SchedulingVariable:
    """
    Represents a variable in the constraint satisfaction problem.
    In scheduling, this is typically a service that needs to be scheduled.
    """

    def __init__(
        self,
        service_id: str,
        service_name: str,
        duration: int,
        buffer_before: int = 0,
        buffer_after: int = 0,
        required_resources: Optional[List[str]] = None,
        required_specialist_ids: Optional[List[str]] = None,
        dependencies: Optional[List[str]] = None,
    ):
        """
        Initialize a scheduling variable.

        Args:
            service_id: Unique identifier for the service
            service_name: Human-readable name of the service
            duration: Duration in minutes
            buffer_before: Buffer time before service in minutes
            buffer_after: Buffer time after service in minutes
            required_resources: Optional list of resource IDs needed for this service
            required_specialist_ids: Optional list of specialist IDs who can perform this service
            dependencies: Optional list of service IDs that must be scheduled before this one
        """
        self.service_id = service_id
        self.service_name = service_name
        self.duration = duration
        self.buffer_before = buffer_before
        self.buffer_after = buffer_after
        self.required_resources = required_resources or []
        self.required_specialist_ids = required_specialist_ids or []
        self.dependencies = dependencies or []
        self.total_duration = duration + buffer_before + buffer_after

    def __str__(self) -> str:
        return f"{self.service_name} ({self.duration}min)"

    def __repr__(self) -> str:
        return (
            f"SchedulingVariable(service_id='{self.service_id}', "
            f"duration={self.duration}, "
            f"buffer_before={self.buffer_before}, "
            f"buffer_after={self.buffer_after})"
        )


class SchedulingDomain:
    """
    Represents the domain of possible values for a scheduling variable.
    In scheduling, this is typically the set of possible time slots.
    """

    def __init__(
        self, variable: SchedulingVariable, available_slots: List[Dict[str, Any]]
    ):
        """
        Initialize a scheduling domain.

        Args:
            variable: The scheduling variable this domain is for
            available_slots: List of available time slots
        """
        self.variable = variable
        self.available_slots = available_slots
        self.current_domain = list(available_slots)  # Copy to allow pruning


class SchedulingAssignment:
    """
    Represents an assignment of a value to a scheduling variable.
    In scheduling, this means assigning a specific time slot to a service.
    """

    def __init__(
        self,
        variable: SchedulingVariable,
        start_time: datetime,
        end_time: datetime,
        specialist_id: Optional[str] = None,
        resources: Optional[List[str]] = None,
    ):
        """
        Initialize a scheduling assignment.

        Args:
            variable: The scheduling variable being assigned
            start_time: Start time of the assignment
            end_time: End time of the assignment
            specialist_id: Optional ID of the specialist assigned
            resources: Optional list of resource IDs assigned
        """
        self.variable = variable
        self.start_time = start_time
        self.end_time = end_time
        self.specialist_id = specialist_id
        self.resources = resources or []

    def __str__(self) -> str:
        return (
            f"{self.variable.service_name}: "
            f"{self.start_time.strftime('%I:%M %p')} - "
            f"{self.end_time.strftime('%I:%M %p')}"
        )

    def total_duration(self) -> int:
        """
        Calculate the total duration including buffer times.

        Returns:
            Total duration in minutes
        """
        total_minutes = int((self.end_time - self.start_time).total_seconds() / 60)
        return total_minutes

    def overlaps(self, other: "SchedulingAssignment") -> bool:
        """
        Check if this assignment overlaps with another.

        Args:
            other: Another scheduling assignment

        Returns:
            True if the assignments overlap in time, False otherwise
        """
        # Account for buffer times
        self_start = self.start_time - timedelta(minutes=self.variable.buffer_before)
        self_end = self.end_time + timedelta(minutes=self.variable.buffer_after)

        other_start = other.start_time - timedelta(minutes=other.variable.buffer_before)
        other_end = other.end_time + timedelta(minutes=other.variable.buffer_after)

        return (self_start < other_end) and (other_start < self_end)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the assignment to a dictionary for API responses.

        Returns:
            Dictionary representation of the assignment
        """
        return {
            "service_id": self.variable.service_id,
            "service_name": self.variable.service_name,
            "start_time": self.start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": self.end_time.strftime("%Y-%m-%d %H:%M:%S"),
            "specialist_id": self.specialist_id,
            "duration": self.variable.duration,
            "buffer_before": self.variable.buffer_before,
            "buffer_after": self.variable.buffer_after,
            "resources": self.resources,
        }


class ConstraintSolver:
    """
    Sophisticated constraint satisfaction solver for complex scheduling problems.
    Uses backtracking with constraint propagation and heuristics to efficiently
    find valid schedules for multiple services with various constraints.
    """

    def __init__(self):
        """Initialize the constraint solver."""
        self.assignments = []
        self.constraints = []

    def solve_multi_service_scheduling(
        self,
        services: List[Dict[str, Any]],
        available_slots_by_service: Dict[str, List[Dict[str, Any]]],
        specialist_availability: Dict[str, List[Dict[str, Any]]],
        resource_availability: Dict[str, List[Dict[str, Any]]],
        date: datetime.date,
        max_solutions: int = 5,
        optimize_for: str = "duration",  # 'duration', 'gaps', 'specialist_preference'
    ) -> List[List[Dict[str, Any]]]:
        """
        Solve a multi-service scheduling problem.

        Args:
            services: List of services to schedule
            available_slots_by_service: Dictionary mapping service IDs to available slots
            specialist_availability: Dictionary mapping specialist IDs to availability
            resource_availability: Dictionary mapping resource IDs to availability
            date: The date for scheduling
            max_solutions: Maximum number of solutions to return
            optimize_for: Optimization criterion ('duration', 'gaps', 'specialist_preference')

        Returns:
            List of possible schedules, each a list of service assignments
        """
        logger.info(
            f"Solving multi-service scheduling for {len(services)} services on {date}"
        )

        # 1. Create scheduling variables for each service
        variables = []
        for service in services:
            variable = SchedulingVariable(
                service_id=service["id"],
                service_name=service["name"],
                duration=service["duration"],
                buffer_before=service.get("buffer_before", 0),
                buffer_after=service.get("buffer_after", 0),
                required_resources=service.get("required_resources", []),
                required_specialist_ids=service.get("required_specialist_ids", []),
                dependencies=service.get("dependencies", []),
            )
            variables.append(variable)

        # 2. Create domains for each variable
        domains = {}
        for variable in variables:
            available_slots = available_slots_by_service.get(variable.service_id, [])
            domains[variable.service_id] = SchedulingDomain(variable, available_slots)

        # 3. Set up the constraint satisfaction problem
        self.assignments = []
        # unused_unused_unused_solution_count = 0  # Kept for potential future use
        all_solutions = []

        # 4. Sort variables by most constrained first (MRV heuristic)
        sorted_variables = self._sort_variables_by_constraints(variables, domains)

        # 5. Solve using backtracking with constraint propagation
        self._backtrack(
            sorted_variables,
            domains,
            specialist_availability,
            resource_availability,
            date,
            0,
            all_solutions,
            max_solutions,
        )

        # 6. If we have solutions, sort them by optimization criterion
        if all_solutions:
            all_solutions = self._rank_solutions(all_solutions, optimize_for)

        # 7. Convert solution assignments to dictionary format
        formatted_solutions = []
        for solution in all_solutions:
            formatted_solution = [assignment.to_dict() for assignment in solution]
            formatted_solutions.append(formatted_solution)

        return formatted_solutions

    def _backtrack(
        self,
        variables: List[SchedulingVariable],
        domains: Dict[str, SchedulingDomain],
        specialist_availability: Dict[str, List[Dict[str, Any]]],
        resource_availability: Dict[str, List[Dict[str, Any]]],
        date: datetime.date,
        depth: int,
        all_solutions: List[List[SchedulingAssignment]],
        max_solutions: int,
    ) -> bool:
        """
        Backtracking algorithm with constraint propagation.

        Args:
            variables: List of variables to assign
            domains: Dictionary of domains for each variable
            specialist_availability: Specialist availability data
            resource_availability: Resource availability data
            date: The scheduling date
            depth: Current depth in the search tree
            all_solutions: List to store found solutions
            max_solutions: Maximum number of solutions to find

        Returns:
            True if a solution was found, False otherwise
        """
        # Check if we've found enough solutions
        if len(all_solutions) >= max_solutions:
            return True

        # Check if we've assigned all variables
        if depth == len(variables):
            # We have a complete assignment, save the solution
            solution = self.assignments.copy()
            all_solutions.append(solution)
            return True

        # Get the next variable to assign
        variable = variables[depth]

        # Try each value in the domain
        for slot in domains[variable.service_id].current_domain:
            # Create a start datetime from the slot
            slot_time = datetime.strptime(slot["start"], "%H:%M").time()
            start_time = datetime.combine(date, slot_time)
            end_time = start_time + timedelta(minutes=variable.duration)

            # Check if all dependencies are satisfied
            if not self._check_dependencies(variable, start_time):
                continue

            # Find an available specialist if needed
            specialist_id = None
            if variable.required_specialist_ids:
                specialist_id = self._find_available_specialist(
                    variable, specialist_availability, start_time, end_time
                )
                if not specialist_id:
                    continue  # No specialist available for this slot

            # Find available resources if needed
            resources = []
            if variable.required_resources:
                resources = self._find_available_resources(
                    variable, resource_availability, start_time, end_time
                )
                if len(resources) < len(variable.required_resources):
                    continue  # Not all required resources available

            # Create a tentative assignment
            assignment = SchedulingAssignment(
                variable=variable,
                start_time=start_time,
                end_time=end_time,
                specialist_id=specialist_id,
                resources=resources,
            )

            # Check if assignment is consistent with current assignments
            if self._is_consistent(assignment):
                # Add the assignment
                self.assignments.append(assignment)

                # Apply constraint propagation
                saved_domains = self._save_domains(domains)
                inference_success = self._forward_checking(domains, assignment, date)

                if inference_success:
                    # Recursively assign the next variable
                    if self._backtrack(
                        variables,
                        domains,
                        specialist_availability,
                        resource_availability,
                        date,
                        depth + 1,
                        all_solutions,
                        max_solutions,
                    ):
                        return True

                # If we get here, we need to backtrack
                # Restore domains and remove the assignment
                self._restore_domains(domains, saved_domains)
                self.assignments.pop()

        # If we tried all values and found no solution
        return False

    def _is_consistent(self, assignment: SchedulingAssignment) -> bool:
        """
        Check if an assignment is consistent with existing assignments.

        Args:
            assignment: The assignment to check

        Returns:
            True if the assignment is consistent, False otherwise
        """
        # Check for conflicts with existing assignments
        for existing in self.assignments:
            # Check for time overlap
            if assignment.overlaps(existing):
                # Check if they use the same specialist
                if (
                    assignment.specialist_id
                    and assignment.specialist_id == existing.specialist_id
                ):
                    return False

                # Check if they use any of the same resources
                if any(
                    resource in existing.resources for resource in assignment.resources
                ):
                    return False

        return True

    def _check_dependencies(
        self, variable: SchedulingVariable, start_time: datetime
    ) -> bool:
        """
        Check if all dependencies for a variable are satisfied.

        Args:
            variable: The variable to check dependencies for
            start_time: The start time of the assignment

        Returns:
            True if all dependencies are satisfied, False otherwise
        """
        if not variable.dependencies:
            return True

        # Check that all dependency services are scheduled before this one
        for dep_id in variable.dependencies:
            dependency_scheduled = False

            for assignment in self.assignments:
                if assignment.variable.service_id == dep_id:
                    # Dependency must be scheduled before this service starts
                    if assignment.end_time <= start_time:
                        dependency_scheduled = True
                        break

            if not dependency_scheduled:
                return False

        return True

    def _find_available_specialist(
        self,
        variable: SchedulingVariable,
        specialist_availability: Dict[str, List[Dict[str, Any]]],
        start_time: datetime,
        end_time: datetime,
    ) -> Optional[str]:
        """
        Find an available specialist for the given time slot.

        Args:
            variable: The service variable
            specialist_availability: Specialist availability data
            start_time: Start time of the assignment
            end_time: End time of the assignment

        Returns:
            ID of an available specialist, or None if none available
        """
        # Account for buffer times
        slot_start = start_time - timedelta(minutes=variable.buffer_before)
        slot_end = end_time + timedelta(minutes=variable.buffer_after)

        # Check each specialist
        for specialist_id in variable.required_specialist_ids:
            # Skip if specialist is already assigned during this time
            specialist_available = True

            for assignment in self.assignments:
                if assignment.specialist_id == specialist_id and assignment.overlaps(
                    SchedulingAssignment(variable, start_time, end_time)
                ):
                    specialist_available = False
                    break

            if not specialist_available:
                continue

            # Check specialist's availability schedule
            availability = specialist_availability.get(specialist_id, [])
            for slot in availability:
                avail_start = datetime.combine(start_time.date(), slot["start_time"])
                avail_end = datetime.combine(start_time.date(), slot["end_time"])

                # If slot is within availability, specialist is available
                if avail_start <= slot_start and avail_end >= slot_end:
                    return specialist_id

        return None

    def _find_available_resources(
        self,
        variable: SchedulingVariable,
        resource_availability: Dict[str, List[Dict[str, Any]]],
        start_time: datetime,
        end_time: datetime,
    ) -> List[str]:
        """
        Find available resources for the given time slot.

        Args:
            variable: The service variable
            resource_availability: Resource availability data
            start_time: Start time of the assignment
            end_time: End time of the assignment

        Returns:
            List of available resource IDs
        """
        available_resources = []

        # Account for buffer times
        slot_start = start_time - timedelta(minutes=variable.buffer_before)
        slot_end = end_time + timedelta(minutes=variable.buffer_after)

        # Try to find each required resource
        for resource_id in variable.required_resources:
            # Skip if resource is already assigned during this time
            resource_available = True

            for assignment in self.assignments:
                if resource_id in assignment.resources and assignment.overlaps(
                    SchedulingAssignment(variable, start_time, end_time)
                ):
                    resource_available = False
                    break

            if not resource_available:
                continue

            # Check resource's availability schedule
            availability = resource_availability.get(resource_id, [])

            for slot in availability:
                avail_start = datetime.combine(start_time.date(), slot["start_time"])
                avail_end = datetime.combine(start_time.date(), slot["end_time"])

                # If slot is within availability, resource is available
                if avail_start <= slot_start and avail_end >= slot_end:
                    available_resources.append(resource_id)
                    break

        return available_resources

    def _forward_checking(
        self,
        domains: Dict[str, SchedulingDomain],
        assignment: SchedulingAssignment,
        date: datetime.date,
    ) -> bool:
        """
        Apply forward checking to reduce domains of unassigned variables.

        Args:
            domains: Dictionary of domains for each variable
            assignment: The newly made assignment
            date: The scheduling date

        Returns:
            True if domains are still valid, False if any domain became empty
        """
        # For each unassigned variable
        for service_id, domain in domains.items():
            # Skip the variable we just assigned
            if service_id == assignment.variable.service_id:
                continue

            # Find the variable in our current assignments
            already_assigned = False
            for assigned in self.assignments:
                if assigned.variable.service_id == service_id:
                    already_assigned = True
                    break

            # Skip variables that are already assigned
            if already_assigned:
                continue

            # Check each value in the domain
            new_domain = []
            for slot in domain.current_domain:
                # Create a start datetime from the slot
                slot_time = datetime.strptime(slot["start"], "%H:%M").time()
                start_time = datetime.combine(date, slot_time)
                end_time = start_time + timedelta(minutes=domain.variable.duration)

                # Create a tentative assignment
                tentative = SchedulingAssignment(
                    variable=domain.variable, start_time=start_time, end_time=end_time
                )

                # Check if this would be consistent with the new assignment
                if not tentative.overlaps(assignment) or (
                    # Allow overlap if not using same specialist or resources
                    assignment.specialist_id is None
                    or assignment.specialist_id
                    not in domain.variable.required_specialist_ids
                ):
                    new_domain.append(slot)

            # Update the domain
            domain.current_domain = new_domain

            # If domain became empty, return failure
            if not domain.current_domain:
                return False

        return True

    def _save_domains(
        self, domains: Dict[str, SchedulingDomain]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Save the current state of all domains for backtracking.

        Args:
            domains: Dictionary of domains

        Returns:
            Dictionary mapping service IDs to copies of their current domains
        """
        saved = {}
        for service_id, domain in domains.items():
            saved[service_id] = list(domain.current_domain)
        return saved

    def _restore_domains(
        self,
        domains: Dict[str, SchedulingDomain],
        saved: Dict[str, List[Dict[str, Any]]],
    ) -> None:
        """
        Restore domains from saved state for backtracking.

        Args:
            domains: Dictionary of domains to restore
            saved: Saved domain state
        """
        for service_id, domain_list in saved.items():
            domains[service_id].current_domain = list(domain_list)

    def _sort_variables_by_constraints(
        self, variables: List[SchedulingVariable], domains: Dict[str, SchedulingDomain]
    ) -> List[SchedulingVariable]:
        """
        Sort variables by most constrained first (MRV heuristic).

        Args:
            variables: List of variables to sort
            domains: Dictionary of domains for each variable

        Returns:
            Sorted list of variables
        """
        # Calculate constraints for each variable
        variable_constraints = []

        for variable in variables:
            # Calculate a constraint score based on:
            # 1. Smaller domain size (fewer options)
            domain_size = len(domains[variable.service_id].current_domain)
            domain_score = 1.0 / max(domain_size, 1)

            # 2. More dependencies
            dependency_score = len(variable.dependencies) * 0.5

            # 3. More required resources or specialists
            resource_score = len(variable.required_resources) * 0.3
            specialist_score = len(variable.required_specialist_ids) * 0.3

            # Combine scores
            constraint_score = (
                domain_score + dependency_score + resource_score + specialist_score
            )

            variable_constraints.append((variable, constraint_score))

        # Sort by constraint score in descending order
        variable_constraints.sort(key=lambda x: x[1], reverse=True)

        # Return the sorted variables
        return [v[0] for v in variable_constraints]

    def _rank_solutions(
        self, solutions: List[List[SchedulingAssignment]], optimize_for: str
    ) -> List[List[SchedulingAssignment]]:
        """
        Rank solutions based on optimization criteria.

        Args:
            solutions: List of solutions to rank
            optimize_for: Optimization criterion

        Returns:
            Ranked list of solutions
        """
        if optimize_for == "duration":
            # Optimize for shortest total duration (from first service start to last service end)
            return sorted(solutions, key=self._calculate_total_duration)

        elif optimize_for == "gaps":
            # Optimize for minimal gaps between services
            return sorted(solutions, key=self._calculate_total_gaps)

        elif optimize_for == "specialist_preference":
            # Optimize for preferred specialists (not implemented here)
            return solutions

        # Default return original order
        return solutions

    def _calculate_total_duration(self, solution: List[SchedulingAssignment]) -> int:
        """
        Calculate the total duration from first service start to last service end.

        Args:
            solution: A list of scheduling assignments

        Returns:
            Total duration in minutes
        """
        if not solution:
            return 0

        # Find earliest start and latest end
        earliest_start = min(a.start_time for a in solution)
        latest_end = max(a.end_time for a in solution)

        # Calculate total minutes
        total_minutes = int((latest_end - earliest_start).total_seconds() / 60)

        return total_minutes

    def _calculate_total_gaps(self, solution: List[SchedulingAssignment]) -> int:
        """
        Calculate the total gap time between services.

        Args:
            solution: A list of scheduling assignments

        Returns:
            Total gap time in minutes
        """
        if len(solution) <= 1:
            return 0

        # Sort assignments by start time
        sorted_assignments = sorted(solution, key=lambda a: a.start_time)

        # Calculate gaps between consecutive services
        total_gap = 0
        for i in range(len(sorted_assignments) - 1):
            current_end = sorted_assignments[i].end_time
            next_start = sorted_assignments[i + 1].start_time

            if next_start > current_end:
                gap_minutes = int((next_start - current_end).total_seconds() / 60)
                total_gap += gap_minutes

        return total_gap
