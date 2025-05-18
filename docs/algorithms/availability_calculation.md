# Availability Calculation Algorithm

## Overview

The Availability Calculation Algorithm is one of the most critical components of the Queue Me platform. It determines when services can be booked based on multiple overlapping constraints including shop hours, service-specific availability, specialist working hours, and existing bookings.

## Algorithm Complexity

This is a constraint satisfaction problem with multiple layers of time-based constraints that must all be satisfied simultaneously for a time slot to be considered "available" for booking.

## Core Components

### 1. Time Domain Definition

The algorithm first establishes the base time domain (the broadest possible range of times):

```python
def get_service_availability(service_id, date):
    service = Service.objects.get(id=service_id)
    shop = service.shop

    # Get weekday (0 = Sunday, 6 = Saturday in our schema)
    weekday = get_adjusted_weekday(date)

    # Get shop operating hours (first constraint)
    shop_hours = ShopHours.objects.get(shop=shop, weekday=weekday)
    if shop_hours.is_closed:
        return []  # Shop is closed on this day

    shop_open = shop_hours.from_hour
    shop_close = shop_hours.to_hour
