## docs/algorithms/queue_optimization.md

```markdown
# Queue Optimization Algorithm

## Overview

The Queue Optimization Algorithm powers Queue Me's innovative hybrid queue management system, enabling businesses to seamlessly handle both scheduled appointments and walk-in customers. This algorithm dynamically manages customer flow, minimizes wait times, and optimizes resource utilization.

## Key Challenges

1. **Hybrid Queue-Appointment Integration**: Merging scheduled appointments with walk-in queues
2. **Real-Time Wait Time Prediction**: Accurately estimating wait times as queue conditions change
3. **Dynamic Resource Allocation**: Balancing staff workload across multiple customers
4. **Priority Management**: Handling VIP customers, urgent cases, and scheduled vs. walk-in priority

## Core Algorithm Components

### 1. Queue Position Management

The foundation of the queue system is a position-based waiting list with dynamic reordering capabilities.

### 2. Adaptive Wait Time Prediction

One of the most sophisticated components is the wait time estimation algorithm that adapts to real-time conditions:

```python
def estimate_wait_time(queue_id, position):
    queue = Queue.objects.get(id=queue_id)

    # Get average service time from recent completions
    recent_tickets = QueueTicket.objects.filter(
        queue=queue,
        status='served',
        complete_time__isnull=False,
        serve_time__isnull=False
    ).order_by('-complete_time')[:20]

    # Calculate average service duration
    avg_service_time = calculate_avg_service_time(recent_tickets)

    # Count tickets ahead in queue
    tickets_ahead = QueueTicket.objects.filter(
        queue=queue,
        position__lt=position,
        status__in=['waiting', 'called']
    ).count()

    # Base wait time calculation
    estimated_wait = tickets_ahead * avg_service_time

    # Adjust for multiple active specialists
    active_specialists = get_active_specialists_count(queue.shop)
    if active_specialists > 1:
        estimated_wait = estimated_wait / active_specialists

    # Apply time-of-day and day-of-week factors
    time_factor = get_time_factors(queue.shop)
    estimated_wait = estimated_wait * time_factor

    return int(estimated_wait)
