"""
Travel time estimation between locations.

This module provides functions for estimating travel time between geographic
locations based on distance, route type, and traffic conditions.
"""

import logging
import math
from typing import Any, Dict, List, Optional, Tuple, Union

from .distance import distance_between

logger = logging.getLogger(__name__)

# Default average speeds in km/h for different road types
DEFAULT_SPEEDS = {
    "urban": 30.0,  # Urban areas
    "suburban": 50.0,  # Suburban areas
    "highway": 90.0,  # Highways
    "rural": 70.0,  # Rural roads
}

# Traffic factors for different times of day
# These are multipliers applied to the base travel time
TRAFFIC_FACTORS = {
    "early_morning": 0.8,  # 5am-7am: Light traffic
    "morning_rush": 1.5,  # 7am-9am: Heavy traffic
    "mid_day": 1.0,  # 9am-4pm: Normal traffic
    "evening_rush": 1.6,  # 4pm-7pm: Heavy traffic
    "evening": 0.9,  # 7pm-11pm: Light traffic
    "night": 0.7,  # 11pm-5am: Very light traffic
}


def estimate_travel_time(
    origin: Union[Dict[str, float], Tuple[float, float]],
    destination: Union[Dict[str, float], Tuple[float, float]],
    road_type: str = "urban",
    traffic_condition: Optional[str] = None,
    time_of_day: Optional[int] = None,
    average_speed: Optional[float] = None,
    with_traffic: bool = True,
    return_minutes: bool = True,
) -> float:
    """
    Estimate travel time between two geographic points.

    Args:
        origin: Starting point as either:
               - dict with 'latitude' and 'longitude' keys, or
               - tuple of (latitude, longitude)
        destination: Ending point in same format as origin
        road_type: Type of road ('urban', 'suburban', 'highway', 'rural')
        traffic_condition: Optional specific traffic condition to override time of day
                       ('light', 'normal', 'heavy', 'very_heavy')
        time_of_day: Optional hour of day (0-23) to determine traffic conditions
        average_speed: Optional override for the average speed in km/h
        with_traffic: Whether to account for traffic conditions
        return_minutes: If True, return time in minutes; otherwise in hours

    Returns:
        Estimated travel time in minutes (or hours if return_minutes=False)
    """
    # Calculate distance in kilometers
    distance_km = distance_between(origin, destination)

    # Determine base speed
    if average_speed is not None:
        speed = average_speed
    else:
        speed = DEFAULT_SPEEDS.get(road_type, DEFAULT_SPEEDS["urban"])

    # Calculate base travel time in hours
    base_time = distance_km / speed

    # Apply traffic factors if requested
    if with_traffic:
        traffic_factor = 1.0

        if traffic_condition:
            # Use explicitly specified traffic condition
            traffic_factors = {
                "light": 0.8,
                "normal": 1.0,
                "heavy": 1.5,
                "very_heavy": 2.0,
            }
            traffic_factor = traffic_factors.get(traffic_condition, 1.0)
        elif time_of_day is not None:
            # Determine traffic factor based on time of day
            if 5 <= time_of_day < 7:
                traffic_factor = TRAFFIC_FACTORS["early_morning"]
            elif 7 <= time_of_day < 9:
                traffic_factor = TRAFFIC_FACTORS["morning_rush"]
            elif 9 <= time_of_day < 16:
                traffic_factor = TRAFFIC_FACTORS["mid_day"]
            elif 16 <= time_of_day < 19:
                traffic_factor = TRAFFIC_FACTORS["evening_rush"]
            elif 19 <= time_of_day < 23:
                traffic_factor = TRAFFIC_FACTORS["evening"]
            else:  # 23-5
                traffic_factor = TRAFFIC_FACTORS["night"]

        # Apply traffic factor to base time
        travel_time = base_time * traffic_factor
    else:
        travel_time = base_time

    # Convert to minutes if requested
    if return_minutes:
        return math.ceil(travel_time * 60)

    return travel_time


def estimate_travel_times_batch(
    origins: List[Union[Dict[str, float], Tuple[float, float]]],
    destinations: List[Union[Dict[str, float], Tuple[float, float]]],
    road_type: str = "urban",
    traffic_condition: Optional[str] = None,
    time_of_day: Optional[int] = None,
    average_speed: Optional[float] = None,
    with_traffic: bool = True,
    return_minutes: bool = True,
) -> List[List[float]]:
    """
    Estimate travel times between multiple origins and destinations.

    Args:
        origins: List of starting points
        destinations: List of ending points
        road_type: Type of road ('urban', 'suburban', 'highway', 'rural')
        traffic_condition: Optional specific traffic condition
        time_of_day: Optional hour of day (0-23)
        average_speed: Optional override for the average speed in km/h
        with_traffic: Whether to account for traffic conditions
        return_minutes: If True, return times in minutes; otherwise in hours

    Returns:
        2D array where result[i][j] is the travel time from origins[i] to destinations[j]
    """
    result = []

    for origin in origins:
        row = []
        for destination in destinations:
            travel_time = estimate_travel_time(
                origin,
                destination,
                road_type,
                traffic_condition,
                time_of_day,
                average_speed,
                with_traffic,
                return_minutes,
            )
            row.append(travel_time)
        result.append(row)

    return result


def estimate_arrival_time(
    origin: Union[Dict[str, float], Tuple[float, float]],
    destination: Union[Dict[str, float], Tuple[float, float]],
    departure_time: int,  # Unix timestamp
    road_type: str = "urban",
    average_speed: Optional[float] = None,
) -> int:
    """
    Estimate arrival time based on departure time and travel time.

    Args:
        origin: Starting point
        destination: Ending point
        departure_time: Unix timestamp for departure
        road_type: Type of road
        average_speed: Optional override for the average speed

    Returns:
        Unix timestamp for estimated arrival
    """
    from datetime import datetime, timedelta

    # Convert timestamp to hour of day
    departure_dt = datetime.fromtimestamp(departure_time)
    hour_of_day = departure_dt.hour

    # Estimate travel time in minutes
    travel_time_mins = estimate_travel_time(
        origin,
        destination,
        road_type,
        time_of_day=hour_of_day,
        average_speed=average_speed,
        return_minutes=True,
    )

    # Calculate arrival time
    arrival_dt = departure_dt + timedelta(minutes=travel_time_mins)
    arrival_timestamp = int(arrival_dt.timestamp())

    return arrival_timestamp


def estimate_eta_for_queue_position(
    customer_location: Union[Dict[str, float], Tuple[float, float]],
    shop_location: Union[Dict[str, float], Tuple[float, float]],
    queue_wait_minutes: int,
    notification_lead_time: int = 15,
    road_type: str = "urban",
) -> Dict[str, Any]:
    """
    Estimate when a customer should leave to arrive on time for their queue position.

    Args:
        customer_location: Customer's location
        shop_location: Shop's location
        queue_wait_minutes: Estimated wait time in minutes until customer's turn
        notification_lead_time: Additional minutes before estimated turn to notify customer
        road_type: Type of road for travel time estimation

    Returns:
        Dictionary with timing information:
        {
            'travel_time_minutes': int,
            'leave_in_minutes': int,
            'should_leave_now': bool
        }
    """
    # Estimate travel time
    travel_time_mins = estimate_travel_time(
        customer_location, shop_location, road_type=road_type, return_minutes=True
    )

    # Calculate when customer should leave
    # Queue wait minus travel time minus notification lead time
    leave_in_minutes = max(
        0, queue_wait_minutes - travel_time_mins - notification_lead_time
    )

    # Determine if customer should leave now
    should_leave_now = leave_in_minutes <= 0

    return {
        "travel_time_minutes": travel_time_mins,
        "leave_in_minutes": leave_in_minutes if not should_leave_now else 0,
        "should_leave_now": should_leave_now,
    }
