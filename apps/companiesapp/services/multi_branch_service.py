"""
Multi-Branch Coordination Service

This module provides sophisticated capabilities for managing and coordinating
multiple branches of a company within the Queue Me platform. It handles centralized
configuration, staff reassignment, resource sharing, and cross-branch analytics.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from django.db import transaction
from django.db.models import Avg, F, Sum
from django.utils import timezone

from apps.bookingapp.models import Appointment
from apps.employeeapp.models import Employee
from apps.rolesapp.models import Role
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop
from apps.specialistsapp.models import Specialist
from core.cache.advanced_cache import AdvancedCache, cached

logger = logging.getLogger(__name__)

# Initialize cache
branch_cache = AdvancedCache("branch")


class MultiBranchService:
    """
    Comprehensive service for managing and coordinating multiple branches
    of a company within the Queue Me platform
    """

    @staticmethod
    @cached(namespace="branch", ttl=300)
    def get_company_branches(company_id: str) -> List[Dict[str, Any]]:
        """
        Get all branches for a company with their key metrics

        Args:
            company_id: Company ID

        Returns:
            List of branch details with metrics
        """
        try:
            # Get all shops/branches for the company
            shops = Shop.objects.filter(company_id=company_id).select_related(
                "location"
            )

            # Get metrics for each branch
            result = []
            for shop in shops:
                # Basic branch details
                branch_info = {
                    "id": str(shop.id),
                    "name": shop.name,
                    "city": shop.location.city if shop.location else None,
                    "address": shop.location.address if shop.location else None,
                    "lat": shop.location.latitude if shop.location else None,
                    "lng": shop.location.longitude if shop.location else None,
                    "is_active": shop.is_active,
                    "created_at": shop.created_at,
                }

                # Count employees
                employee_count = Employee.objects.filter(shop_id=shop.id).count()
                specialist_count = Specialist.objects.filter(shop_id=shop.id).count()

                # Count services
                service_count = Service.objects.filter(shop_id=shop.id).count()

                # Recent booking metrics
                recent_bookings = Appointment.objects.filter(
                    shop_id=shop.id, created_at__gte=timezone.now() - timedelta(days=30)
                )
                booking_count = recent_bookings.count()

                # Get average rating if available
                try:
                    from apps.reviewapp.models import Review

                    avg_rating = (
                        Review.objects.filter(shop_id=shop.id).aggregate(
                            avg_rating=Avg("rating")
                        )["avg_rating"]
                        or 0
                    )
                except Exception:
                    avg_rating = 0

                # Add metrics to branch info
                branch_info.update(
                    {
                        "employee_count": employee_count,
                        "specialist_count": specialist_count,
                        "service_count": service_count,
                        "recent_booking_count": booking_count,
                        "avg_rating": avg_rating,
                    }
                )

                result.append(branch_info)

            return result

        except Exception as e:
            logger.error(f"Error getting company branches: {e}")
            return []

    @staticmethod
    def apply_template_to_branch(
        template_branch_id: str,
        target_branch_id: str,
        include_services: bool = True,
        include_roles: bool = True,
        include_settings: bool = True,
    ) -> Dict[str, Any]:
        """
        Apply configuration from a template branch to another branch

        Args:
            template_branch_id: Source branch ID to use as template
            target_branch_id: Target branch ID to apply template to
            include_services: Whether to copy service definitions
            include_roles: Whether to copy role definitions
            include_settings: Whether to copy shop settings

        Returns:
            Results of the template application
        """
        try:
            # Start database transaction to ensure consistency
            with transaction.atomic():
                # Get source and target branches
                try:
                    template_branch = Shop.objects.get(id=template_branch_id)
                    target_branch = Shop.objects.get(id=target_branch_id)
                except Shop.DoesNotExist:
                    return {
                        "success": False,
                        "message": "Template or target branch not found",
                    }

                # Check if branches belong to the same company
                if template_branch.company_id != target_branch.company_id:
                    return {
                        "success": False,
                        "message": "Template and target branches must belong to the same company",
                    }

                results = {
                    "services_copied": 0,
                    "roles_copied": 0,
                    "settings_applied": False,
                }

                # Apply service template if requested
                if include_services:
                    results["services_copied"] = MultiBranchService._copy_services(
                        template_branch_id, target_branch_id
                    )

                # Apply role template if requested
                if include_roles:
                    results["roles_copied"] = MultiBranchService._copy_roles(
                        template_branch_id, target_branch_id
                    )

                # Apply settings template if requested
                if include_settings:
                    results["settings_applied"] = MultiBranchService._copy_settings(
                        template_branch_id, target_branch_id
                    )

                # Update target branch
                target_branch.template_applied = True
                target_branch.template_source_id = template_branch_id
                target_branch.template_applied_at = timezone.now()
                target_branch.save()

                return {
                    "success": True,
                    "message": "Template applied successfully",
                    "results": results,
                }

        except Exception as e:
            logger.error(f"Error applying branch template: {e}")
            return {"success": False, "message": f"Error applying template: {str(e)}"}

    @staticmethod
    def reassign_staff_to_branch(
        staff_ids: List[str],
        target_branch_id: str,
        transfer_roles: bool = True,
        maintain_services: bool = True,
    ) -> Dict[str, Any]:
        """
        Reassign staff members to a different branch

        Args:
            staff_ids: List of staff/employee IDs to reassign
            target_branch_id: Target branch ID to reassign to
            transfer_roles: Whether to maintain staff roles
            maintain_services: Whether specialists should keep service assignments

        Returns:
            Results of the reassignment operation
        """
        try:
            # Start database transaction to ensure consistency
            with transaction.atomic():
                # Get target branch
                try:
                    target_branch = Shop.objects.get(id=target_branch_id)
                except Shop.DoesNotExist:
                    return {"success": False, "message": "Target branch not found"}

                # Track results
                results = {
                    "employees_reassigned": 0,
                    "specialists_reassigned": 0,
                    "services_maintained": 0,
                    "roles_transferred": 0,
                    "failed_ids": [],
                }

                # Process each employee
                for staff_id in staff_ids:
                    try:
                        # Get employee
                        employee = Employee.objects.get(id=staff_id)

                        # Store original branch ID for service lookup
                        employee.shop_id

                        # Check if employee belongs to the same company
                        if employee.shop.company_id != target_branch.company_id:
                            results["failed_ids"].append(staff_id)
                            continue

                        # Update employee branch
                        employee.shop_id = target_branch_id
                        employee.save()
                        results["employees_reassigned"] += 1

                        # Handle role transfer if requested
                        if transfer_roles:
                            # Get employee's roles in previous branch
                            from apps.rolesapp.models import RoleAssignment

                            role_assignments = RoleAssignment.objects.filter(
                                employee_id=staff_id
                            )

                            # For each role, check if it exists in target branch
                            for assignment in role_assignments:
                                # Get role details
                                role = assignment.role

                                # Find equivalent role in target branch
                                try:
                                    target_role = Role.objects.get(
                                        shop_id=target_branch_id, name=role.name
                                    )

                                    # Create new role assignment
                                    RoleAssignment.objects.create(
                                        employee_id=staff_id, role=target_role
                                    )

                                    results["roles_transferred"] += 1
                                except Role.DoesNotExist:
                                    # Role doesn't exist in target branch, could create it
                                    pass

                        # Handle specialist service assignments if applicable
                        if maintain_services and hasattr(employee, "specialist"):
                            specialist = employee.specialist
                            results["specialists_reassigned"] += 1

                            # Get specialist's service assignments
                            from apps.specialistsapp.models import SpecialistService

                            service_assignments = SpecialistService.objects.filter(
                                specialist=specialist
                            )

                            # For each service, find equivalent in new branch
                            for assignment in service_assignments:
                                # Get original service
                                original_service = assignment.service

                                # Find equivalent service in target branch
                                try:
                                    target_service = Service.objects.get(
                                        shop_id=target_branch_id,
                                        name=original_service.name,
                                        category=original_service.category,
                                    )

                                    # Create new service assignment
                                    SpecialistService.objects.create(
                                        specialist=specialist,
                                        service=target_service,
                                        is_preferred=assignment.is_preferred,
                                        experience_level=assignment.experience_level,
                                    )

                                    results["services_maintained"] += 1
                                except Service.DoesNotExist:
                                    # Service doesn't exist in target branch
                                    pass

                    except Employee.DoesNotExist:
                        results["failed_ids"].append(staff_id)
                    except Exception as e:
                        logger.error(f"Error reassigning staff {staff_id}: {e}")
                        results["failed_ids"].append(staff_id)

                return {
                    "success": True,
                    "message": f"Reassigned {results['employees_reassigned']} employees to branch {target_branch.name}",
                    "results": results,
                }

        except Exception as e:
            logger.error(f"Error reassigning staff to branch: {e}")
            return {"success": False, "message": f"Error reassigning staff: {str(e)}"}

    @staticmethod
    def get_cross_branch_analytics(
        company_id: str,
        date_from: datetime,
        date_to: datetime,
        metrics: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Get analytics across all branches for comparison

        Args:
            company_id: Company ID
            date_from: Start date for analytics period
            date_to: End date for analytics period
            metrics: List of metrics to include, or None for all

        Returns:
            Dictionary with cross-branch analytics
        """
        try:
            # Get all branches for company
            branches = Shop.objects.filter(company_id=company_id)

            if not branches:
                return {"success": False, "message": "No branches found for company"}

            # Default metrics if not specified
            if not metrics:
                metrics = [
                    "booking_count",
                    "revenue",
                    "avg_rating",
                    "service_count",
                    "specialist_count",
                    "customer_count",
                ]

            # Initialize result
            result = {
                "company_id": company_id,
                "date_range": {
                    "from": date_from.isoformat(),
                    "to": date_to.isoformat(),
                },
                "branches": {},
                "totals": {},
            }

            # Initialize totals
            totals = {metric: 0 for metric in metrics}
            branch_data = {}

            # Process each branch
            for branch in branches:
                branch_id = str(branch.id)
                branch_metrics = {}

                # Get bookings for the period
                bookings = Appointment.objects.filter(
                    shop_id=branch_id,
                    start_time__gte=date_from,
                    start_time__lte=date_to,
                )

                # Calculate metrics
                if "booking_count" in metrics:
                    booking_count = bookings.count()
                    branch_metrics["booking_count"] = booking_count
                    totals["booking_count"] += booking_count

                if "revenue" in metrics:
                    revenue = (
                        bookings.filter(payment_status="paid").aggregate(
                            total=Sum(F("service__price"))
                        )["total"]
                        or 0
                    )
                    branch_metrics["revenue"] = float(revenue)
                    totals["revenue"] += float(revenue)

                if "avg_rating" in metrics:
                    try:
                        from apps.reviewapp.models import Review

                        avg_rating = (
                            Review.objects.filter(
                                shop_id=branch_id,
                                created_at__gte=date_from,
                                created_at__lte=date_to,
                            ).aggregate(avg=Avg("rating"))["avg"]
                            or 0
                        )
                        branch_metrics["avg_rating"] = float(avg_rating)
                        # Don't sum avg_rating for totals
                    except Exception:
                        branch_metrics["avg_rating"] = 0

                if "service_count" in metrics:
                    service_count = Service.objects.filter(shop_id=branch_id).count()
                    branch_metrics["service_count"] = service_count
                    totals["service_count"] += service_count

                if "specialist_count" in metrics:
                    specialist_count = Specialist.objects.filter(
                        shop_id=branch_id
                    ).count()
                    branch_metrics["specialist_count"] = specialist_count
                    totals["specialist_count"] += specialist_count

                if "customer_count" in metrics:
                    customer_count = bookings.values("customer_id").distinct().count()
                    branch_metrics["customer_count"] = customer_count
                    totals["customer_count"] += customer_count

                # Add branch data to result
                branch_data[branch_id] = {
                    "name": branch.name,
                    "metrics": branch_metrics,
                }

            # Calculate averages for relevant metrics
            if "avg_rating" in metrics and len(branches) > 0:
                totals["avg_rating"] = sum(
                    b["metrics"].get("avg_rating", 0) for b in branch_data.values()
                ) / len(branches)

            # Add data to result
            result["branches"] = branch_data
            result["totals"] = totals

            return {"success": True, "data": result}

        except Exception as e:
            logger.error(f"Error getting cross-branch analytics: {e}")
            return {
                "success": False,
                "message": f"Error calculating analytics: {str(e)}",
            }

    @staticmethod
    def get_staff_allocation_suggestions(company_id: str) -> Dict[str, Any]:
        """
        Get suggestions for optimizing staff allocation across branches

        Args:
            company_id: Company ID

        Returns:
            Suggestions for staff allocation optimization
        """
        try:
            # Get all branches for company
            branches = Shop.objects.filter(company_id=company_id)

            if not branches.exists():
                return {"success": False, "message": "No branches found for company"}

            # Get upcoming bookings for all branches (next 7 days)
            date_from = timezone.now()
            date_to = date_from + timedelta(days=7)

            # Get bookings by branch and day
            branch_booking_data = {}
            specialist_utilization = {}

            # Get all specialists for this company
            specialists = Specialist.objects.filter(
                shop__company_id=company_id
            ).select_related("shop", "employee")

            # Process each branch
            for branch in branches:
                branch_id = str(branch.id)

                # Get bookings for this branch
                bookings = Appointment.objects.filter(
                    shop_id=branch_id,
                    start_time__gte=date_from,
                    start_time__lte=date_to,
                )

                # Group bookings by day
                bookings_by_day = {}
                for booking in bookings:
                    day = booking.start_time.date()
                    if day not in bookings_by_day:
                        bookings_by_day[day] = []
                    bookings_by_day[day].append(booking)

                # Store branch booking data
                branch_booking_data[branch_id] = {
                    "name": branch.name,
                    "bookings_by_day": bookings_by_day,
                    "total_bookings": bookings.count(),
                    "specialists": specialists.filter(shop_id=branch_id).count(),
                }

                # Calculate specialist utilization
                branch_specialists = specialists.filter(shop_id=branch_id)
                for specialist in branch_specialists:
                    specialist_id = str(specialist.id)
                    specialist_bookings = bookings.filter(specialist_id=specialist_id)

                    if specialist_id not in specialist_utilization:
                        specialist_utilization[specialist_id] = {
                            "name": (
                                specialist.employee.name
                                if hasattr(specialist, "employee")
                                else f"Specialist {specialist_id}"
                            ),
                            "branch_id": branch_id,
                            "branch_name": branch.name,
                            "bookings": specialist_bookings.count(),
                            "services": specialist.specialist_services.count(),
                            "hours_booked": 0,
                        }

                    # Calculate booked hours
                    hours_booked = 0
                    for booking in specialist_bookings:
                        if booking.start_time and booking.end_time:
                            duration = (
                                booking.end_time - booking.start_time
                            ).total_seconds() / 3600
                            hours_booked += duration

                    specialist_utilization[specialist_id]["hours_booked"] = hours_booked

            # Calculate branch load and identify overloaded/underloaded branches
            branch_load = {}
            total_bookings = sum(
                data["total_bookings"] for data in branch_booking_data.values()
            )
            total_specialists = sum(
                data["specialists"] for data in branch_booking_data.values()
            )

            if total_bookings == 0 or total_specialists == 0:
                return {
                    "success": True,
                    "message": "Insufficient booking data for meaningful suggestions",
                    "data": {"branches": branch_booking_data, "suggestions": []},
                }

            # Calculate expected bookings per specialist
            expected_bookings_per_specialist = (
                total_bookings / total_specialists if total_specialists > 0 else 0
            )

            # Calculate load factor for each branch
            for branch_id, data in branch_booking_data.items():
                if data["specialists"] > 0:
                    bookings_per_specialist = (
                        data["total_bookings"] / data["specialists"]
                    )
                    load_factor = (
                        bookings_per_specialist / expected_bookings_per_specialist
                        if expected_bookings_per_specialist > 0
                        else 0
                    )

                    branch_load[branch_id] = {
                        "name": data["name"],
                        "load_factor": load_factor,
                        "bookings_per_specialist": bookings_per_specialist,
                        "is_overloaded": load_factor > 1.2,  # 20% over average
                        "is_underloaded": load_factor < 0.8,  # 20% under average
                    }

            # Generate suggestions
            suggestions = []

            # Find overloaded and underloaded branches
            overloaded_branches = [
                branch_id
                for branch_id, data in branch_load.items()
                if data["is_overloaded"]
            ]

            underloaded_branches = [
                branch_id
                for branch_id, data in branch_load.items()
                if data["is_underloaded"]
            ]

            # Find underutilized specialists in overloaded branches
            for branch_id in overloaded_branches:
                # Get specialists in this branch
                branch_specialists = [
                    specialist_id
                    for specialist_id, data in specialist_utilization.items()
                    if data["branch_id"] == branch_id
                ]

                # Sort by utilization (ascending)
                branch_specialists.sort(
                    key=lambda s_id: specialist_utilization[s_id]["hours_booked"]
                )

                # Identify candidates for transfer
                candidates = branch_specialists[: max(1, len(branch_specialists) // 3)]

                for candidate in candidates:
                    specialist_data = specialist_utilization[candidate]

                    # Only suggest moves for significantly underutilized specialists
                    hours_booked = specialist_data["hours_booked"]
                    if hours_booked < 10:  # Less than 10 hours booked in next 7 days
                        # Find best underloaded branch
                        if underloaded_branches:
                            target_branch_id = min(
                                underloaded_branches,
                                key=lambda b_id: branch_load[b_id]["load_factor"],
                            )

                            suggestions.append(
                                {
                                    "type": "specialist_transfer",
                                    "specialist_id": candidate,
                                    "specialist_name": specialist_data["name"],
                                    "source_branch_id": branch_id,
                                    "source_branch_name": branch_load[branch_id][
                                        "name"
                                    ],
                                    "target_branch_id": target_branch_id,
                                    "target_branch_name": branch_load[target_branch_id][
                                        "name"
                                    ],
                                    "reason": f"Specialist has only {hours_booked:.1f} hours booked in the next 7 days, "
                                    + f"while branch {branch_load[branch_id]['name']} is overloaded",
                                    "priority": (
                                        "high" if hours_booked < 5 else "medium"
                                    ),
                                }
                            )

            return {
                "success": True,
                "data": {"branch_load": branch_load, "suggestions": suggestions},
            }

        except Exception as e:
            logger.error(f"Error generating staff allocation suggestions: {e}")
            return {
                "success": False,
                "message": f"Error generating suggestions: {str(e)}",
            }

    # ---- Private Helper Methods ----

    @staticmethod
    def _copy_services(template_branch_id: str, target_branch_id: str) -> int:
        """Copy services from template branch to target branch"""
        # Get services from template branch
        template_services = Service.objects.filter(shop_id=template_branch_id)
        services_copied = 0

        # Process each service
        for template_service in template_services:
            # Check if service with same name already exists
            existing_service = Service.objects.filter(
                shop_id=target_branch_id,
                name=template_service.name,
                category=template_service.category,
            ).first()

            if not existing_service:
                # Create new service based on template
                new_service = Service.objects.create(
                    shop_id=target_branch_id,
                    name=template_service.name,
                    description=template_service.description,
                    price=template_service.price,
                    duration=template_service.duration,
                    category=template_service.category,
                    slot_granularity=template_service.slot_granularity,
                    buffer_before=template_service.buffer_before,
                    buffer_after=template_service.buffer_after,
                    location_type=template_service.location_type,
                    min_booking_notice=template_service.min_booking_notice,
                    max_booking_days_ahead=template_service.max_booking_days_ahead,
                    is_active=template_service.is_active,
                )

                # Copy service images if any
                if (
                    hasattr(template_service, "images")
                    and template_service.images.exists()
                ):
                    from apps.serviceapp.models import ServiceImage

                    for image in template_service.images.all():
                        ServiceImage.objects.create(
                            service=new_service, image=image.image, order=image.order
                        )

                services_copied += 1

        return services_copied

    @staticmethod
    def _copy_roles(template_branch_id: str, target_branch_id: str) -> int:
        """Copy custom roles from template branch to target branch"""
        # Get roles from template branch
        template_roles = Role.objects.filter(shop_id=template_branch_id)
        roles_copied = 0

        # Process each role
        for template_role in template_roles:
            # Check if role with same name already exists
            existing_role = Role.objects.filter(
                shop_id=target_branch_id, name=template_role.name
            ).first()

            if not existing_role:
                # Create new role based on template
                new_role = Role.objects.create(
                    shop_id=target_branch_id,
                    name=template_role.name,
                    description=template_role.description,
                    permissions=template_role.permissions,
                    is_active=template_role.is_active,
                )

                roles_copied += 1

        return roles_copied

    @staticmethod
    def _copy_settings(template_branch_id: str, target_branch_id: str) -> bool:
        """Copy settings from template branch to target branch"""
        try:
            # Get template branch
            template_branch = Shop.objects.get(id=template_branch_id)
            target_branch = Shop.objects.get(id=target_branch_id)

            # Copy relevant settings
            target_branch.opening_time = template_branch.opening_time
            target_branch.closing_time = template_branch.closing_time
            target_branch.working_days = template_branch.working_days
            target_branch.break_start_time = template_branch.break_start_time
            target_branch.break_end_time = template_branch.break_end_time
            target_branch.notification_settings = template_branch.notification_settings
            target_branch.booking_settings = template_branch.booking_settings
            target_branch.queue_settings = template_branch.queue_settings

            # Don't copy unique/identity information
            # target_branch.name = template_branch.name
            # target_branch.location = template_branch.location

            target_branch.save()
            return True

        except Exception as e:
            logger.error(f"Error copying settings: {e}")
            return False
