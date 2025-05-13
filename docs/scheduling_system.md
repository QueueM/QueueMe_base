# QueueMe Advanced Scheduling System

This document provides a comprehensive overview of the advanced scheduling system implemented in QueueMe, explaining the architecture, components, algorithms, and interactions between different services.

## Table of Contents

1. [System Overview](#system-overview)
2. [Core Components](#core-components)
3. [Algorithms and Strategies](#algorithms-and-strategies)
4. [Service Interactions](#service-interactions)
5. [Scheduling Workflows](#scheduling-workflows)
6. [Optimization Techniques](#optimization-techniques)
7. [Extensibility](#extensibility)

## System Overview

The QueueMe scheduling system is designed to efficiently manage appointments between customers and specialists while optimizing resource allocation. The system handles complex constraints such as specialist availability, service requirements, resource availability, and customer preferences.

Key features include:
- Dynamic calculation of availability based on multiple constraints
- Smart conflict detection and prevention
- Intelligent specialist allocation based on multiple criteria
- Buffer time management to ensure smooth transitions
- Support for scheduling multiple services sequentially
- Multiple scheduling optimization strategies
- Real-time adaptation to changes

## Core Components

The scheduling system consists of several interconnected services, each responsible for a specific aspect of the scheduling process:

### 1. Availability Service (`availability_service.py`)

Calculates available time slots based on multiple constraints:
- Shop operating hours
- Service availability windows
- Specialist working hours
- Existing bookings
- Service duration and buffer times
- Custom blocked time periods

The service uses efficient time range intersection algorithms to quickly determine valid slots even with many constraints.

### 2. Conflict Detection Service (`conflict_detection_service.py`)

Identifies and prevents booking conflicts related to:
- Specialist scheduling
- Resource allocation
- Room/location availability
- Service capacity
- Overlapping service dependencies

This service ensures the integrity of the scheduling system by preventing double-bookings and resource conflicts.

### 3. Buffer Management Service (`buffer_management_service.py`)

Manages buffer times between appointments:
- Calculates required buffer times before and after services
- Enforces buffer time constraints
- Provides optimal buffer time recommendations
- Resolves buffer time conflicts
- Adapts buffer times based on service complexity

### 4. Specialist Allocation Service (`specialist_allocation_service.py`)

Optimally allocates specialists to appointments based on multiple criteria:
- Workload balancing across specialists
- Skill-based matching
- Customer preferences
- Wait time optimization
- Specialist performance metrics

The service uses a weighted scoring algorithm to find the most suitable specialist for each appointment.

### 5. Scheduling Optimizer (`scheduling_optimizer.py`)

High-level orchestration service that:
- Coordinates the other services
- Implements different scheduling strategies
- Manages multi-service bookings
- Handles rescheduling and cancellations
- Optimizes overall scheduling efficiency

## Algorithms and Strategies

### Availability Calculation

The availability calculation algorithm employs a sophisticated approach:

1. **Constraint Collection**: Gather all constraints (shop hours, service availability, specialist hours)
2. **Time Range Intersection**: Find overlapping periods across all constraints
3. **Slot Generation**: Convert continuous availability into discrete slots based on service duration and granularity
4. **Conflict Filtering**: Filter out slots that conflict with existing bookings
5. **Buffer Time Application**: Apply buffer times to ensure adequate preparation and cleanup

```python
# Pseudo-code for availability calculation
def calculate_availability(shop, service, date, specialist=None):
    # Get shop operating hours for the day
    shop_hours = get_shop_hours(shop, date)

    # Get service availability windows
    service_windows = get_service_availability(service, date)

    # Intersect shop hours and service windows
    base_availability = intersect_time_ranges(shop_hours, service_windows)

    # If specialist specified, apply specialist constraints
    if specialist:
        specialist_hours = get_specialist_hours(specialist, date)
        base_availability = intersect_time_ranges(base_availability, specialist_hours)
        existing_bookings = get_specialist_bookings(specialist, date)
    else:
        # Find any available specialist
        specialists = get_service_specialists(service)
        available_slots = []
        for s in specialists:
            # Process each specialist's availability
            # Merge results

    # Generate discrete slots based on service duration and buffer times
    slots = generate_slots(base_availability, service.duration,
                         service.buffer_before, service.buffer_after,
                         existing_bookings)

    return slots
```

### Specialist Allocation

The specialist allocation algorithm uses a weighted scoring approach to find the optimal specialist:

1. **Candidate Filtering**: Filter specialists based on service capability, working hours, and availability
2. **Multi-dimensional Scoring**:
   - Workload score (30%): Balance workload among specialists
   - Skills score (25%): Match specialist skills to service requirements
   - Customer preference score (20%): Consider customer preferences and past experiences
   - Wait time score (15%): Minimize customer waiting time
   - Performance score (10%): Factor in specialist efficiency and ratings
3. **Weighted Aggregation**: Combine scores with appropriate weights
4. **Rank and Select**: Select the specialist with the highest overall score

### Scheduling Strategies

The system supports multiple scheduling strategies:

1. **Earliest Available**: Book at the earliest possible time with any available specialist
2. **Balanced Workload**: Distribute bookings evenly among specialists to balance workload
3. **Minimize Wait**: Prioritize minimizing customer wait time
4. **Resource Efficient**: Optimize resource utilization by minimizing fragmentation

## Service Interactions

The scheduling services interact in a hierarchical manner:

1. **Top Level**: `SchedulingOptimizer` orchestrates the overall process
2. **Middle Level**: `SpecialistAllocationService` and `BufferManagementService` provide specialized functionality
3. **Base Level**: `AvailabilityService` and `ConflictDetectionService` provide fundamental scheduling capabilities

### Typical Interaction Flow

```
┌─────────────────────────┐
│                         │
│  SchedulingOptimizer    │◄────────┐
│                         │         │
└───────────┬─────────────┘         │
            │                       │
            ▼                       │
┌─────────────────────────┐         │
│                         │         │
│SpecialistAllocationSvc  │         │
│                         │         │
└───────────┬─────────────┘         │
            │                       │
            ▼                       │
┌─────────────────────────┐         │
│                         │         │
│ BufferManagementService │         │
│                         │         │
└─────────┬───────────────┘         │
          │                         │
┌─────────▼───────────┐   ┌─────────▼───────────┐
│                     │   │                     │
│ AvailabilityService │   │ConflictDetectionSvc │
│                     │   │                     │
└─────────────────────┘   └─────────────────────┘
```

## Scheduling Workflows

### Single Appointment Booking

1. User selects service, date, and optionally time and specialist
2. System calculates available slots using `AvailabilityService`
3. If specialist not specified, system finds optimal specialist using `SpecialistAllocationService`
4. System checks for conflicts using `ConflictDetectionService`
5. System calculates buffer requirements using `BufferManagementService`
6. `SchedulingOptimizer` creates the appointment with the appropriate resources

### Multi-Service Booking

1. User selects multiple services, date, and optionally specialist
2. System determines optimal sequencing of services
3. For sequential booking:
   - Services are scheduled back-to-back with appropriate buffer times
   - System attempts to keep the same specialist when possible
4. For independent booking:
   - Each service is scheduled independently
   - System may assign different specialists based on availability and skills

### Rescheduling

1. User requests to reschedule an appointment
2. System validates new time and specialist availability
3. System checks for conflicts in the new time slot
4. If conflicts exist, system suggests alternative times
5. System updates the appointment and reallocates resources if needed

## Optimization Techniques

The scheduling system employs several optimization techniques:

### Caching

- Availability results are cached with appropriate TTL
- Common calculation results are cached to avoid redundant processing
- Cache invalidation occurs on appointment creation/modification

### Database Query Optimization

- Efficient queries with proper indexing
- Selective loading of related data through `select_related` and `prefetch_related`
- Query batching to reduce database roundtrips

### Resource Allocation Optimization

- Resource sharing between appointments when possible
- Minimizing resource fragmentation
- Smart reallocation during rescheduling

### Workload Balancing

- Even distribution of appointments among specialists
- Consideration of service complexity when balancing workload
- Adaptive adjustment based on specialist performance

## Extensibility

The scheduling system is designed to be extensible:

### Adding New Constraints

New scheduling constraints can be added by extending the `AvailabilityService` and `ConflictDetectionService` with additional checks.

### New Allocation Strategies

Additional specialist allocation strategies can be implemented by:
1. Adding new scoring factors to `SpecialistAllocationService`
2. Adjusting the weights of existing factors
3. Implementing custom score calculation methods

### New Scheduling Strategies

New scheduling strategies can be added to `SchedulingOptimizer` by implementing additional strategy methods and registering them as available strategies.

### Integration with External Systems

The scheduling system can be integrated with external systems through:
- API endpoints for availability and booking
- Event hooks for appointment creation, modification, and cancellation
- Data synchronization for external calendars

## Summary

The QueueMe advanced scheduling system provides a sophisticated, flexible, and efficient solution for managing appointments. Its modular design allows for easy extension and customization, while its optimization features ensure efficient resource utilization and a balanced workload for specialists.
