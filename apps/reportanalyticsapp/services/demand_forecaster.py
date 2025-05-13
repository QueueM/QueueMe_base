# apps/reportanalyticsapp/services/demand_forecaster.py
"""
Demand Forecaster Service

Predictive analytics system for forecasting future service demand
based on historical booking patterns, considering seasonality,
shop capacity, and external factors.
"""

import math
from datetime import timedelta

from django.db.models import Count, F, FloatField, Sum
from django.db.models.functions import Extract, TruncDay
from django.utils import timezone

from apps.bookingapp.models import Appointment
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop
from apps.specialistsapp.models import Specialist, SpecialistService
from core.cache.cache_manager import cache_with_key_prefix


class DemandForecaster:
    """
    Service for forecasting demand for services across various dimensions,
    using advanced predictive algorithms and historical data analysis.
    """

    @staticmethod
    @cache_with_key_prefix("booking_forecast", timeout=3600)  # Cache for 1 hour
    def forecast_bookings(shop_id, days_ahead=14, service_id=None, specialist_id=None):
        """
        Forecast future bookings for a shop, optionally filtered by service or specialist.

        Args:
            shop_id (uuid): The shop ID to analyze
            days_ahead (int): Number of days to forecast
            service_id (uuid, optional): Filter by service
            specialist_id (uuid, optional): Filter by specialist

        Returns:
            dict: Forecast data for each day in the forecast period
        """
        # Get shop
        try:
            shop = Shop.objects.get(id=shop_id)
        except Shop.DoesNotExist:
            return {"error": "Shop not found"}

        # Set up date ranges
        end_date = timezone.now()
        start_date = end_date - timedelta(days=90)  # Use 90 days of historical data

        # Get historical data
        historical_data = DemandForecaster._get_historical_booking_data(
            shop_id, start_date, end_date, service_id, specialist_id
        )

        if not historical_data:
            return {
                "error": "Insufficient historical data for forecasting",
                "shop_id": shop_id,
            }

        # Generate forecast dates
        forecast_dates = []
        forecast_start = end_date.date() + timedelta(days=1)

        for i in range(days_ahead):
            forecast_date = forecast_start + timedelta(days=i)
            forecast_dates.append(forecast_date)

        # Calculate forecast for each date
        forecast_data = []

        for forecast_date in forecast_dates:
            # Get day of week (0 = Monday, 6 = Sunday)
            weekday = forecast_date.weekday()

            # Adjust to 0 = Sunday
            weekday = (weekday + 1) % 7

            # Get month
            month = forecast_date.month

            # Calculate forecast using time series decomposition
            forecast = DemandForecaster._calculate_booking_forecast(
                historical_data, weekday, month, forecast_date
            )

            # Check for special events or holidays
            # In a real implementation, this would check against a calendar of events
            # For simplicity, we'll assume no special events

            forecast_data.append(
                {
                    "date": forecast_date.isoformat(),
                    "weekday": [
                        "Monday",
                        "Tuesday",
                        "Wednesday",
                        "Thursday",
                        "Friday",
                        "Saturday",
                        "Sunday",
                    ][weekday],
                    "forecast_bookings": forecast["bookings"],
                    "forecast_revenue": forecast["revenue"],
                    "confidence": forecast["confidence"],
                    "factors": forecast["factors"],
                }
            )

        return {
            "shop_id": str(shop_id),
            "service_id": str(service_id) if service_id else None,
            "specialist_id": str(specialist_id) if specialist_id else None,
            "start_date": forecast_start.isoformat(),
            "end_date": (forecast_start + timedelta(days=days_ahead - 1)).isoformat(),
            "forecast": forecast_data,
        }

    @staticmethod
    def predict_demand_heatmap(shop_id, service_id=None):
        """
        Generate a demand heatmap showing predicted booking intensity by day of week and hour.

        Args:
            shop_id (uuid): The shop ID to analyze
            service_id (uuid, optional): Filter by service

        Returns:
            dict: Heatmap data showing predicted booking intensity
        """
        # Get shop
        try:
            shop = Shop.objects.get(id=shop_id)
        except Shop.DoesNotExist:
            return {"error": "Shop not found"}

        # Set up date ranges for historical data
        end_date = timezone.now()
        start_date = end_date - timedelta(days=90)  # Use 90 days of historical data

        # Get historical appointments
        appointments = Appointment.objects.filter(
            shop_id=shop_id, start_time__gte=start_date, start_time__lte=end_date
        )

        if service_id:
            appointments = appointments.filter(service_id=service_id)

        # Group by day of week and hour
        appointments = (
            appointments.annotate(
                weekday=Extract("start_time", "dow"), hour=Extract("start_time", "hour")
            )
            .values("weekday", "hour")
            .annotate(count=Count("id"))
            .order_by("weekday", "hour")
        )

        # Initialize heatmap data
        heatmap_data = {}

        for weekday in range(7):  # 0 = Sunday, 6 = Saturday
            day_name = [
                "Sunday",
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
            ][weekday]
            heatmap_data[day_name] = {}

            for hour in range(24):
                heatmap_data[day_name][hour] = 0

        # Populate heatmap data
        max_count = 0

        for appointment in appointments:
            weekday = appointment["weekday"]
            hour = appointment["hour"]
            count = appointment["count"]

            day_name = [
                "Sunday",
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
            ][weekday]
            heatmap_data[day_name][hour] = count

            if count > max_count:
                max_count = count

        # Calculate intensity (0-100) for each cell
        for day, hours in heatmap_data.items():
            for hour, count in hours.items():
                if max_count > 0:
                    intensity = (count / max_count) * 100
                else:
                    intensity = 0

                heatmap_data[day][hour] = {
                    "count": count,
                    "intensity": round(intensity, 2),
                }

        # Get shop operating hours for context
        operating_hours = {}

        from apps.shopapp.models import ShopHours

        for weekday in range(7):
            day_name = [
                "Sunday",
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
            ][weekday]

            try:
                hours = ShopHours.objects.get(shop=shop, weekday=weekday)

                if hours.is_closed:
                    operating_hours[day_name] = {"is_closed": True}
                else:
                    operating_hours[day_name] = {
                        "is_closed": False,
                        "from_hour": hours.from_hour.strftime("%H:%M"),
                        "to_hour": hours.to_hour.strftime("%H:%M"),
                    }
            except ShopHours.DoesNotExist:
                operating_hours[day_name] = {"is_closed": True}

        return {
            "shop_id": str(shop_id),
            "service_id": str(service_id) if service_id else None,
            "max_count": max_count,
            "heatmap": heatmap_data,
            "operating_hours": operating_hours,
        }

    @staticmethod
    def predict_specialist_utilization(shop_id, days_ahead=14):
        """
        Predict specialist utilization rates for future days.

        Args:
            shop_id (uuid): The shop ID to analyze
            days_ahead (int): Number of days to forecast

        Returns:
            dict: Forecast of specialist utilization
        """
        # Get shop
        try:
            shop = Shop.objects.get(id=shop_id)
        except Shop.DoesNotExist:
            return {"error": "Shop not found"}

        # Get specialists
        specialists = Specialist.objects.filter(employee__shop_id=shop_id, employee__is_active=True)

        if not specialists.exists():
            return {"error": "No active specialists found", "shop_id": shop_id}

        # Set up date ranges
        end_date = timezone.now()
        start_date = end_date - timedelta(days=90)  # Use 90 days of historical data

        # Generate forecast dates
        forecast_dates = []
        forecast_start = end_date.date() + timedelta(days=1)

        for i in range(days_ahead):
            forecast_date = forecast_start + timedelta(days=i)
            forecast_dates.append(forecast_date)

        # Get historical utilization by specialist
        specialist_utilization = DemandForecaster._get_historical_specialist_utilization(
            specialists, start_date, end_date
        )

        # Calculate forecast for each specialist
        forecast_data = []

        for forecast_date in forecast_dates:
            day_forecast = {
                "date": forecast_date.isoformat(),
                "weekday": forecast_date.strftime("%A"),
                "specialists": [],
            }

            for specialist in specialists:
                # Get day of week (0 = Monday, 6 = Sunday)
                weekday = forecast_date.weekday()

                # Adjust to 0 = Sunday
                weekday = (weekday + 1) % 7

                # Calculate forecast
                specialist_forecast = DemandForecaster._forecast_specialist_utilization(
                    specialist,
                    specialist_utilization.get(str(specialist.id), {}),
                    weekday,
                )

                day_forecast["specialists"].append(
                    {
                        "id": str(specialist.id),
                        "name": f"{specialist.employee.first_name} {specialist.employee.last_name}",
                        "forecasted_utilization": specialist_forecast["utilization"],
                        "forecasted_appointments": specialist_forecast["appointments"],
                        "confidence": specialist_forecast["confidence"],
                    }
                )

            forecast_data.append(day_forecast)

        return {
            "shop_id": str(shop_id),
            "start_date": forecast_start.isoformat(),
            "end_date": (forecast_start + timedelta(days=days_ahead - 1)).isoformat(),
            "forecast": forecast_data,
        }

    @staticmethod
    def predict_revenue(shop_id, days_ahead=30):
        """
        Predict daily revenue for future days.

        Args:
            shop_id (uuid): The shop ID to analyze
            days_ahead (int): Number of days to forecast

        Returns:
            dict: Revenue forecast data
        """
        # Get shop
        try:
            shop = Shop.objects.get(id=shop_id)
        except Shop.DoesNotExist:
            return {"error": "Shop not found"}

        # Set up date ranges
        end_date = timezone.now()
        start_date = end_date - timedelta(
            days=365
        )  # Use 1 year of historical data for better seasonality detection

        # Get historical revenue data
        revenue_data = DemandForecaster._get_historical_revenue_data(shop_id, start_date, end_date)

        if not revenue_data:
            return {
                "error": "Insufficient historical data for revenue forecasting",
                "shop_id": shop_id,
            }

        # Generate forecast dates
        forecast_dates = []
        forecast_start = end_date.date() + timedelta(days=1)

        for i in range(days_ahead):
            forecast_date = forecast_start + timedelta(days=i)
            forecast_dates.append(forecast_date)

        # Calculate forecast for each date using time series decomposition
        forecast_data = []
        cumulative_revenue = 0

        for forecast_date in forecast_dates:
            forecast = DemandForecaster._calculate_revenue_forecast(revenue_data, forecast_date)
            cumulative_revenue += forecast["revenue"]

            forecast_data.append(
                {
                    "date": forecast_date.isoformat(),
                    "weekday": forecast_date.strftime("%A"),
                    "forecast_revenue": round(forecast["revenue"], 2),
                    "confidence_interval": {
                        "lower": round(forecast["revenue"] * (1 - forecast["error_margin"]), 2),
                        "upper": round(forecast["revenue"] * (1 + forecast["error_margin"]), 2),
                    },
                    "factors": forecast["factors"],
                }
            )

        return {
            "shop_id": str(shop_id),
            "start_date": forecast_start.isoformat(),
            "end_date": (forecast_start + timedelta(days=days_ahead - 1)).isoformat(),
            "total_forecast_revenue": round(cumulative_revenue, 2),
            "forecast": forecast_data,
        }

    @staticmethod
    def recommend_pricing_adjustments(shop_id):
        """
        Recommend service pricing adjustments based on demand patterns and competitor analysis.

        Args:
            shop_id (uuid): The shop ID to analyze

        Returns:
            dict: Pricing recommendations
        """
        # Get shop
        try:
            shop = Shop.objects.get(id=shop_id)
        except Shop.DoesNotExist:
            return {"error": "Shop not found"}

        # Get services
        services = Service.objects.filter(shop_id=shop_id, is_active=True)

        if not services.exists():
            return {"error": "No active services found", "shop_id": shop_id}

        # Set up date ranges
        end_date = timezone.now()
        start_date = end_date - timedelta(days=90)  # Use 90 days of data

        # Analyze each service
        recommendations = []

        for service in services:
            # Get bookings
            bookings = Appointment.objects.filter(
                service=service, start_time__gte=start_date, start_time__lte=end_date
            )

            # Calculate metrics
            booking_count = bookings.count()

            if booking_count == 0:
                continue  # Skip services with no bookings

            # Calculate booking rate (bookings per day)
            days = (end_date - start_date).days
            booking_rate = booking_count / days

            # Calculate utilization (% of capacity)
            # For simplicity, we'll estimate capacity
            capacity = DemandForecaster._estimate_service_capacity(service, days)
            utilization = (booking_count / capacity) * 100 if capacity > 0 else 0

            # Get competitor pricing (if available)
            competitor_pricing = DemandForecaster._get_competitor_pricing(service)

            # Make recommendation based on utilization and competitor pricing
            recommendation = DemandForecaster._calculate_pricing_recommendation(
                service, utilization, competitor_pricing
            )

            recommendations.append(
                {
                    "service_id": str(service.id),
                    "service_name": service.name,
                    "current_price": service.price,
                    "booking_count": booking_count,
                    "booking_rate": round(booking_rate, 2),
                    "utilization": round(utilization, 2),
                    "competitor_avg_price": (
                        competitor_pricing["average"] if competitor_pricing else None
                    ),
                    "recommendation": recommendation,
                }
            )

        return {
            "shop_id": str(shop_id),
            "analysis_period": {
                "start_date": start_date.date().isoformat(),
                "end_date": end_date.date().isoformat(),
            },
            "recommendations": recommendations,
        }

    # Private helper methods

    @staticmethod
    def _get_historical_booking_data(
        shop_id, start_date, end_date, service_id=None, specialist_id=None
    ):
        """Get historical booking data for analysis"""
        # Get appointments
        appointments = Appointment.objects.filter(
            shop_id=shop_id, start_time__gte=start_date, start_time__lte=end_date
        )

        if service_id:
            appointments = appointments.filter(service_id=service_id)

        if specialist_id:
            appointments = appointments.filter(specialist_id=specialist_id)

        # Group by day
        daily_data = (
            appointments.annotate(
                date=TruncDay("start_time"),
                weekday=Extract("start_time", "dow"),
                month=Extract("start_time", "month"),
            )
            .values("date", "weekday", "month")
            .annotate(
                booking_count=Count("id"),
                revenue=Sum(F("service__price"), output_field=FloatField()),
            )
            .order_by("date")
        )

        # Format data
        result = []

        for day in daily_data:
            result.append(
                {
                    "date": day["date"].date(),
                    "weekday": day["weekday"],
                    "month": day["month"],
                    "booking_count": day["booking_count"],
                    "revenue": day["revenue"] or 0,
                }
            )

        return result

    @staticmethod
    def _calculate_booking_forecast(historical_data, weekday, month, forecast_date):
        """Calculate booking forecast using time series decomposition"""
        # Calculate average by day of week
        weekday_data = [day for day in historical_data if day["weekday"] == weekday]

        if not weekday_data:
            return {"bookings": 0, "revenue": 0, "confidence": 0, "factors": []}

        weekday_avg_bookings = sum(day["booking_count"] for day in weekday_data) / len(weekday_data)
        weekday_avg_revenue = sum(day["revenue"] for day in weekday_data) / len(weekday_data)

        # Calculate monthly seasonality factor
        month_data = [day for day in historical_data if day["month"] == month]

        if month_data:
            month_avg_bookings = sum(day["booking_count"] for day in month_data) / len(month_data)
            overall_avg_bookings = sum(day["booking_count"] for day in historical_data) / len(
                historical_data
            )

            if overall_avg_bookings > 0:
                month_factor = month_avg_bookings / overall_avg_bookings
            else:
                month_factor = 1.0
        else:
            month_factor = 1.0

        # Calculate trend
        if len(historical_data) >= 30:
            # Split into two halves
            half_point = len(historical_data) // 2
            first_half = historical_data[:half_point]
            second_half = historical_data[half_point:]

            first_half_avg = sum(day["booking_count"] for day in first_half) / len(first_half)
            second_half_avg = sum(day["booking_count"] for day in second_half) / len(second_half)

            # Calculate trend factor
            if first_half_avg > 0:
                trend_factor = second_half_avg / first_half_avg
            else:
                trend_factor = 1.0
        else:
            trend_factor = 1.0

        # Forecast bookings
        forecast_bookings = weekday_avg_bookings * month_factor * trend_factor

        # Forecast revenue
        if weekday_avg_bookings > 0:
            forecast_revenue = (weekday_avg_revenue / weekday_avg_bookings) * forecast_bookings
        else:
            forecast_revenue = 0

        # Calculate confidence based on data quality
        data_points = len(weekday_data)
        confidence = min(
            0.9, max(0.1, (data_points / 20))
        )  # Scale from 0.1 to 0.9 based on data points

        # Adjust for specific factors
        factors = []

        # Check for day before/after weekend
        if weekday in [0, 6]:  # Sunday or Saturday
            forecast_bookings *= 0.9  # Weekend adjustment
            factors.append({"name": "Weekend", "impact": -10})

        # Check for month-end
        if 25 <= forecast_date.day <= 31:
            forecast_bookings *= 0.95  # Month-end adjustment
            factors.append({"name": "Month end", "impact": -5})

        # For further improvement, additional factors could be considered:
        # - Special events
        # - Holidays
        # - Weather effects
        # - Marketing campaigns

        return {
            "bookings": round(forecast_bookings),
            "revenue": round(forecast_revenue, 2),
            "confidence": round(confidence, 2),
            "factors": factors,
        }

    @staticmethod
    def _get_historical_specialist_utilization(specialists, start_date, end_date):
        """Calculate historical utilization rates for specialists"""
        result = {}

        for specialist in specialists:
            # Get working hours
            from apps.specialistsapp.models import SpecialistWorkingHours

            working_hours = SpecialistWorkingHours.objects.filter(
                specialist=specialist, is_off=False
            )

            # Get appointments
            appointments = Appointment.objects.filter(
                specialist=specialist,
                start_time__gte=start_date,
                start_time__lte=end_date,
            ).annotate(date=TruncDay("start_time"), weekday=Extract("start_time", "dow"))

            # Calculate utilization by weekday
            utilization_by_weekday = {}
            appointments_by_weekday = {}

            for weekday in range(7):
                weekday_appointments = appointments.filter(weekday=weekday)

                # Get working hours for this weekday
                try:
                    wh = working_hours.get(weekday=weekday)

                    # Calculate working minutes
                    from_hour = wh.from_hour.hour * 60 + wh.from_hour.minute
                    to_hour = wh.to_hour.hour * 60 + wh.to_hour.minute

                    total_minutes = to_hour - from_hour

                    if total_minutes <= 0:
                        utilization_by_weekday[weekday] = 0
                        appointments_by_weekday[weekday] = 0
                        continue

                    # Calculate booked minutes
                    booked_minutes = sum(
                        appointment.service.duration
                        + appointment.service.buffer_before
                        + appointment.service.buffer_after
                        for appointment in weekday_appointments
                    )

                    # Calculate utilization
                    utilization = (booked_minutes / total_minutes) * 100

                    utilization_by_weekday[weekday] = utilization
                    appointments_by_weekday[weekday] = weekday_appointments.count()

                except SpecialistWorkingHours.DoesNotExist:
                    utilization_by_weekday[weekday] = 0
                    appointments_by_weekday[weekday] = 0

            result[str(specialist.id)] = {
                "utilization_by_weekday": utilization_by_weekday,
                "appointments_by_weekday": appointments_by_weekday,
            }

        return result

    @staticmethod
    def _forecast_specialist_utilization(specialist, historical_data, weekday):
        """Forecast utilization for a specialist on a specific weekday"""
        if not historical_data or "utilization_by_weekday" not in historical_data:
            return {"utilization": 0, "appointments": 0, "confidence": 0}

        # Get historical utilization for this weekday
        utilization = historical_data["utilization_by_weekday"].get(weekday, 0)
        appointments = historical_data["appointments_by_weekday"].get(weekday, 0)

        # For simplicity, we'll return the historical data
        # In a more advanced implementation, we could apply trend analysis
        # and other forecasting techniques

        # Calculate confidence based on consistency of data
        confidence = 0.7  # Default

        return {
            "utilization": round(utilization, 2),
            "appointments": appointments,
            "confidence": confidence,
        }

    @staticmethod
    def _get_historical_revenue_data(shop_id, start_date, end_date):
        """Get historical revenue data for analysis"""
        # Get completed appointments
        appointments = Appointment.objects.filter(
            shop_id=shop_id,
            start_time__gte=start_date,
            start_time__lte=end_date,
            status="completed",
        )

        # Group by day
        daily_revenue = (
            appointments.annotate(
                date=TruncDay("start_time"),
                weekday=Extract("start_time", "dow"),
                month=Extract("start_time", "month"),
            )
            .values("date", "weekday", "month")
            .annotate(revenue=Sum("service__price"))
            .order_by("date")
        )

        # Format data
        result = []

        for day in daily_revenue:
            result.append(
                {
                    "date": day["date"].date(),
                    "weekday": day["weekday"],
                    "month": day["month"],
                    "revenue": day["revenue"] or 0,
                }
            )

        return result

    @staticmethod
    def _calculate_revenue_forecast(historical_data, forecast_date):
        """Calculate revenue forecast for a specific date"""
        # Get day of week (0 = Monday, 6 = Sunday)
        weekday = forecast_date.weekday()

        # Adjust to 0 = Sunday
        weekday = (weekday + 1) % 7

        # Get month
        month = forecast_date.month

        # Calculate average by day of week
        weekday_data = [day for day in historical_data if day["weekday"] == weekday]

        if not weekday_data:
            return {"revenue": 0, "error_margin": 0.5, "factors": []}

        weekday_avg_revenue = sum(day["revenue"] for day in weekday_data) / len(weekday_data)

        # Calculate monthly seasonality factor
        month_data = [day for day in historical_data if day["month"] == month]

        if month_data:
            month_avg_revenue = sum(day["revenue"] for day in month_data) / len(month_data)
            overall_avg_revenue = sum(day["revenue"] for day in historical_data) / len(
                historical_data
            )

            if overall_avg_revenue > 0:
                month_factor = month_avg_revenue / overall_avg_revenue
            else:
                month_factor = 1.0
        else:
            month_factor = 1.0

        # Calculate trend
        if len(historical_data) >= 30:
            # Split into two halves
            half_point = len(historical_data) // 2
            first_half = historical_data[:half_point]
            second_half = historical_data[half_point:]

            first_half_avg = sum(day["revenue"] for day in first_half) / len(first_half)
            second_half_avg = sum(day["revenue"] for day in second_half) / len(second_half)

            # Calculate trend factor
            if first_half_avg > 0:
                trend_factor = second_half_avg / first_half_avg
            else:
                trend_factor = 1.0
        else:
            trend_factor = 1.0

        # Forecast revenue
        forecast_revenue = weekday_avg_revenue * month_factor * trend_factor

        # Calculate error margin based on historical variance
        if len(weekday_data) > 1:
            weekday_revenues = [day["revenue"] for day in weekday_data]
            mean = sum(weekday_revenues) / len(weekday_revenues)
            variance = sum((x - mean) ** 2 for x in weekday_revenues) / len(weekday_revenues)
            std_dev = math.sqrt(variance)

            coefficient_of_variation = std_dev / mean if mean > 0 else 0.5
            error_margin = min(
                0.5, max(0.1, coefficient_of_variation)
            )  # Constrain between 0.1 and 0.5
        else:
            error_margin = 0.3  # Default if not enough data

        # Adjust for specific factors
        factors = []

        # Check for day before/after weekend
        if weekday in [0, 6]:  # Sunday or Saturday
            forecast_revenue *= 1.1  # Weekend adjustment
            factors.append({"name": "Weekend", "impact": 10})

        # Check for month-end
        if 25 <= forecast_date.day <= 31:
            forecast_revenue *= 0.9  # Month-end adjustment
            factors.append({"name": "Month end", "impact": -10})

        # The revenue model could be enhanced with external factors:
        # - Holidays
        # - Special events
        # - Marketing campaigns
        # - Economic indicators

        return {
            "revenue": forecast_revenue,
            "error_margin": error_margin,
            "factors": factors,
        }

    @staticmethod
    def _estimate_service_capacity(service, days):
        """Estimate service capacity over a period"""
        # Get service shop
        # unused_unused_shop = service.shop

        # Get specialists for this service
        specialist_count = SpecialistService.objects.filter(service=service).count()

        if specialist_count == 0:
            return 0  # No specialists, no capacity

        # Get service duration (including buffers)
        total_service_time = service.duration + service.buffer_before + service.buffer_after

        # Estimate daily capacity (simplistic approach)
        # Assuming 8 hours of operation per day and all specialists working full time
        daily_minutes_per_specialist = 8 * 60  # 8 hours in minutes

        daily_slots_per_specialist = daily_minutes_per_specialist / total_service_time

        daily_capacity = daily_slots_per_specialist * specialist_count

        # Total capacity over the period
        capacity = daily_capacity * days

        return capacity

    @staticmethod
    def _get_competitor_pricing(service):
        """Get competitor pricing for similar services"""
        # In a real implementation, this would analyze similar services in nearby shops
        # For simplicity, we'll return synthetic data

        shop = service.shop
        category = service.category

        # Get similar services in the same category from other shops

        if shop.location:
            # Get shops in the same city
            nearby_shops = Shop.objects.filter(location__city=shop.location.city).exclude(
                id=shop.id
            )

            similar_services = Service.objects.filter(
                shop__in=nearby_shops, category=category, is_active=True
            )

            if similar_services.exists():
                prices = [s.price for s in similar_services]

                return {
                    "average": sum(prices) / len(prices),
                    "min": min(prices),
                    "max": max(prices),
                    "count": len(prices),
                }

        # Default if no data
        return None

    @staticmethod
    def _calculate_pricing_recommendation(service, utilization, competitor_pricing):
        """Calculate pricing recommendation based on utilization and competitor pricing"""
        current_price = service.price

        # Initialize recommendation
        recommendation = {
            "action": "maintain",
            "suggested_price": current_price,
            "change_percent": 0,
            "reasoning": [],
        }

        # Analyze based on utilization
        if utilization >= 90:
            # High utilization - can consider price increase
            recommendation["action"] = "increase"
            price_change_pct = 10  # 10% increase
            recommendation["reasoning"].append(
                "High service utilization (90%+) indicates strong demand"
            )
        elif utilization >= 70:
            # Good utilization - maintain price
            recommendation["action"] = "maintain"
            price_change_pct = 0
            recommendation["reasoning"].append(
                "Good service utilization (70-90%) suggests appropriate pricing"
            )
        elif utilization >= 50:
            # Moderate utilization - maintain or small decrease
            recommendation["action"] = "maintain"
            price_change_pct = 0
            recommendation["reasoning"].append(
                "Moderate utilization (50-70%) suggests appropriate pricing"
            )
        elif utilization >= 30:
            # Low utilization - consider price decrease
            recommendation["action"] = "decrease"
            price_change_pct = -5  # 5% decrease
            recommendation["reasoning"].append(
                "Low utilization (30-50%) suggests price may be too high for demand"
            )
        else:
            # Very low utilization - significant price decrease
            recommendation["action"] = "decrease"
            price_change_pct = -15  # 15% decrease
            recommendation["reasoning"].append(
                "Very low utilization (<30%) suggests significant price barrier"
            )

        # Adjust based on competitor pricing (if available)
        if competitor_pricing:
            avg_competitor_price = competitor_pricing["average"]
            # unused_unused_min_competitor_price = competitor_pricing["min"]
            # unused_unused_max_competitor_price = competitor_pricing["max"]

            price_difference_pct = (
                ((current_price - avg_competitor_price) / avg_competitor_price) * 100
                if avg_competitor_price > 0
                else 0
            )

            if price_difference_pct > 20:
                # Much higher than competitors
                recommendation["reasoning"].append(
                    f"Current price is {round(price_difference_pct, 1)}% higher than competitors' average"
                )
                if recommendation["action"] != "decrease":
                    recommendation["action"] = "decrease"
                    price_change_pct = -10  # 10% decrease
            elif price_difference_pct < -20:
                # Much lower than competitors
                recommendation["reasoning"].append(
                    f"Current price is {round(-price_difference_pct, 1)}% lower than competitors' average"
                )
                if utilization >= 70:
                    # Low price + high utilization = opportunity to increase
                    recommendation["action"] = "increase"
                    price_change_pct = 15  # 15% increase
            else:
                # Within competitive range
                recommendation["reasoning"].append(
                    "Current price is within 20% of competitors' average"
                )

        # Calculate suggested price
        suggested_price = current_price * (1 + price_change_pct / 100)

        # Round to nearest 5 SAR for pricing aesthetics
        suggested_price = round(suggested_price / 5) * 5

        # Ensure minimum price
        suggested_price = max(suggested_price, 5)  # Minimum 5 SAR

        # Calculate actual change percentage
        actual_change_pct = ((suggested_price - current_price) / current_price) * 100

        recommendation["suggested_price"] = suggested_price
        recommendation["change_percent"] = round(actual_change_pct, 1)

        # Update action based on final calculation
        if recommendation["change_percent"] > 0:
            recommendation["action"] = "increase"
        elif recommendation["change_percent"] < 0:
            recommendation["action"] = "decrease"
        else:
            recommendation["action"] = "maintain"

        return recommendation
