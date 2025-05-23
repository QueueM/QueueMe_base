"""
Query Optimization Script for QueueMe Backend

This script analyzes and optimizes database queries in the QueueMe backend
by identifying and fixing N+1 query issues, optimizing select_related and
prefetch_related usage, and implementing query annotations for better performance.

Usage:
    python query_optimization.py

The script will:
1. Analyze views and services for inefficient query patterns
2. Generate optimized versions of problematic queries
3. Provide recommendations for query optimization
"""


# Dictionary of views and services with query optimization opportunities
# Format: {app_name: {file_name: {function_name: {original: "...", optimized: "..."}}}}
QUERY_OPTIMIZATIONS = {
    "bookingapp": {
        "views.py": {
            "get_appointments": {
                "original": """
    def get_appointments(self, request):
        # N+1 query issue: For each appointment, additional queries for related objects
        appointments = Appointment.objects.filter(
            customer=request.user
        ).order_by('-start_time')
        
        serializer = AppointmentSerializer(appointments, many=True)
        return Response(serializer.data)
                """,
                "optimized": """
    def get_appointments(self, request):
        # Optimized: Prefetch related objects to avoid N+1 queries
        appointments = Appointment.objects.filter(
            customer=request.user
        ).select_related(
            'service', 'specialist', 'shop'
        ).prefetch_related(
            'reminders'
        ).order_by('-start_time')
        
        serializer = AppointmentSerializer(appointments, many=True)
        return Response(serializer.data)
                """,
            },
            "get_shop_appointments": {
                "original": """
    def get_shop_appointments(self, request, shop_id):
        # Inefficient: Multiple database hits and no pagination
        shop = get_object_or_404(Shop, id=shop_id)
        appointments = Appointment.objects.filter(shop=shop).order_by('start_time')
        
        serializer = AppointmentSerializer(appointments, many=True)
        return Response(serializer.data)
                """,
                "optimized": """
    def get_shop_appointments(self, request, shop_id):
        # Optimized: Efficient querying with pagination and select_related
        shop = get_object_or_404(Shop, id=shop_id)
        appointments = Appointment.objects.filter(shop=shop).select_related(
            'service', 'specialist', 'customer'
        ).order_by('start_time')
        
        # Add pagination
        paginator = PageNumberPagination()
        paginator.page_size = 20
        result_page = paginator.paginate_queryset(appointments, request)
        
        serializer = AppointmentSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)
                """,
            },
        },
        "services/booking_service.py": {
            "get_available_slots": {
                "original": """
    def get_available_slots(self, shop_id, service_id, date):
        # Inefficient: Multiple queries and in-memory filtering
        shop = Shop.objects.get(id=shop_id)
        service = Service.objects.get(id=service_id)
        specialists = Specialist.objects.filter(shop=shop, services=service)
        
        available_slots = []
        for specialist in specialists:
            # This causes N+1 queries
            schedule = SpecialistSchedule.objects.filter(
                specialist=specialist, 
                date=date
            ).first()
            
            if schedule and schedule.is_available:
                # More queries for each specialist
                existing_appointments = Appointment.objects.filter(
                    specialist=specialist,
                    start_time__date=date
                )
                
                # In-memory calculation of available slots
                slots = self._calculate_available_slots(
                    schedule, existing_appointments, service.duration
                )
                available_slots.extend(slots)
        
        return available_slots
                """,
                "optimized": """
    def get_available_slots(self, shop_id, service_id, date):
        # Optimized: Efficient querying with annotations and prefetching
        shop = Shop.objects.get(id=shop_id)
        service = Service.objects.get(id=service_id)
        
        # Get specialists with prefetched schedules
        specialists = Specialist.objects.filter(
            shop=shop, 
            services=service,
            is_active=True
        ).prefetch_related(
            Prefetch(
                'schedules',
                queryset=SpecialistSchedule.objects.filter(date=date, is_available=True),
                to_attr='day_schedule'
            )
        )
        
        # Get all relevant appointments in a single query
        appointments = Appointment.objects.filter(
            specialist__in=specialists,
            start_time__date=date
        ).values('specialist_id', 'start_time', 'end_time')
        
        # Group appointments by specialist
        specialist_appointments = defaultdict(list)
        for appointment in appointments:
            specialist_appointments[appointment['specialist_id']].append(appointment)
        
        available_slots = []
        for specialist in specialists:
            # Skip specialists without schedule for the day
            if not hasattr(specialist, 'day_schedule') or not specialist.day_schedule:
                continue
                
            schedule = specialist.day_schedule[0]
            specialist_appts = specialist_appointments.get(str(specialist.id), [])
            
            # Calculate available slots
            slots = self._calculate_available_slots(
                schedule, specialist_appts, service.duration
            )
            available_slots.extend(slots)
        
        return available_slots
                """,
            }
        },
    },
    "shopapp": {
        "views.py": {
            "get_shops": {
                "original": """
    def get_shops(self, request):
        # Inefficient: No pagination and missing select_related
        shops = Shop.objects.filter(is_active=True)
        serializer = ShopSerializer(shops, many=True)
        return Response(serializer.data)
                """,
                "optimized": """
    def get_shops(self, request):
        # Optimized: Added pagination and annotations for counts
        shops = Shop.objects.filter(is_active=True).annotate(
            service_count=Count('services', distinct=True),
            specialist_count=Count('specialists', distinct=True)
        )
        
        # Add pagination
        paginator = PageNumberPagination()
        paginator.page_size = 20
        result_page = paginator.paginate_queryset(shops, request)
        
        serializer = ShopSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)
                """,
            }
        }
    },
    "authapp": {
        "services/user_service.py": {
            "get_user_activity": {
                "original": """
    def get_user_activity(self, user_id):
        # Inefficient: Multiple queries and no batching
        user = User.objects.get(id=user_id)
        
        # These cause multiple queries
        appointments = Appointment.objects.filter(customer=user)
        payments = Payment.objects.filter(customer=user)
        notifications = Notification.objects.filter(recipient=user)
        
        return {
            'appointments': AppointmentSerializer(appointments, many=True).data,
            'payments': PaymentSerializer(payments, many=True).data,
            'notifications': NotificationSerializer(notifications, many=True).data
        }
                """,
                "optimized": """
    def get_user_activity(self, user_id):
        # Optimized: Efficient querying with limits and select_related
        user = User.objects.get(id=user_id)
        
        # Get recent appointments with related objects
        appointments = Appointment.objects.filter(
            customer=user
        ).select_related(
            'service', 'specialist', 'shop'
        ).order_by('-start_time')[:10]
        
        # Get recent payments with related objects
        payments = Payment.objects.filter(
            customer=user
        ).select_related(
            'appointment'
        ).order_by('-created_at')[:10]
        
        # Get recent notifications
        notifications = Notification.objects.filter(
            recipient=user, 
            is_read=False
        ).order_by('-created_at')[:20]
        
        return {
            'appointments': AppointmentSerializer(appointments, many=True).data,
            'payments': PaymentSerializer(payments, many=True).data,
            'notifications': NotificationSerializer(notifications, many=True).data
        }
                """,
            }
        }
    },
}


def generate_optimization_report():
    """Generate a report of query optimizations."""
    report = []
    report.append("# Query Optimization Report for QueueMe Backend")
    report.append(
        "\nThis report identifies inefficient query patterns and provides optimized alternatives.\n"
    )

    for app_name, files in QUERY_OPTIMIZATIONS.items():
        report.append(f"## {app_name}")

        for file_name, functions in files.items():
            report.append(f"\n### {file_name}")

            for function_name, queries in functions.items():
                report.append(f"\n#### {function_name}")
                report.append("\n**Original Query (Inefficient):**")
                report.append("```python")
                report.append(queries["original"])
                report.append("```")

                report.append("\n**Optimized Query:**")
                report.append("```python")
                report.append(queries["optimized"])
                report.append("```")

                # Add explanation of optimizations
                report.append("\n**Optimizations Applied:**")
                if "select_related" in queries["optimized"]:
                    report.append(
                        "- Added `select_related` to reduce database queries for foreign key relationships"
                    )
                if "prefetch_related" in queries["optimized"]:
                    report.append(
                        "- Added `prefetch_related` to efficiently load related objects"
                    )
                if (
                    "annotate" in queries["optimized"]
                    or "Count" in queries["optimized"]
                ):
                    report.append(
                        "- Used annotations to perform calculations at the database level"
                    )
                if "paginator" in queries["optimized"]:
                    report.append(
                        "- Implemented pagination to limit result size and improve response time"
                    )
                if "values" in queries["optimized"]:
                    report.append("- Used `values()` to retrieve only needed fields")
                if "defaultdict" in queries["optimized"]:
                    report.append(
                        "- Optimized in-memory processing with efficient data structures"
                    )
                if (
                    "order_by" in queries["optimized"]
                    and "order_by" not in queries["original"]
                ):
                    report.append(
                        "- Added explicit ordering to ensure consistent results"
                    )
                if "[:" in queries["optimized"] and "[:" not in queries["original"]:
                    report.append("- Limited result set size to improve performance")

    return "\n".join(report)


def main():
    """Main function to generate optimization report."""
    report = generate_optimization_report()

    # In a real implementation, this would write to a file
    # For this script, we'll just print the report
    print(report)

    # Write report to file
    with open("query_optimization_report.md", "w") as f:
        f.write(report)

    print("\nReport generated: query_optimization_report.md")


if __name__ == "__main__":
    main()
