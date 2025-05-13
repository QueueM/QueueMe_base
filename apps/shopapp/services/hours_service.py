from datetime import datetime, time, timedelta

from django.db import transaction
from django.utils import timezone

from apps.shopapp.models import Shop, ShopHours


class HoursService:
    @staticmethod
    @transaction.atomic
    def create_default_hours(shop_id):
        """Create default hours for a shop"""
        shop = Shop.objects.get(id=shop_id)

        # Delete any existing hours
        ShopHours.objects.filter(shop=shop).delete()

        # Create default hours (9 AM - 6 PM, closed on Friday)
        for weekday in range(7):
            ShopHours.objects.create(
                shop=shop,
                weekday=weekday,
                from_hour=time(9, 0),  # 9:00 AM
                to_hour=time(18, 0),  # 6:00 PM
                is_closed=(weekday == 5),  # Closed on Friday
            )

    @staticmethod
    @transaction.atomic
    def update_shop_hours(shop_id, hours_data):
        """Update shop operating hours"""
        shop = Shop.objects.get(id=shop_id)

        for hour_data in hours_data:
            weekday = hour_data.get("weekday")

            # Validate weekday
            if weekday is None or not (0 <= weekday <= 6):
                raise ValueError("Invalid weekday. Must be between 0 (Sunday) and 6 (Saturday).")

            # Get or create shop hour for this weekday
            shop_hour, created = ShopHours.objects.get_or_create(
                shop=shop,
                weekday=weekday,
                defaults={
                    "from_hour": hour_data.get("from_hour"),
                    "to_hour": hour_data.get("to_hour"),
                    "is_closed": hour_data.get("is_closed", False),
                },
            )

            if not created:
                # Update existing record
                if "from_hour" in hour_data:
                    shop_hour.from_hour = hour_data["from_hour"]
                if "to_hour" in hour_data:
                    shop_hour.to_hour = hour_data["to_hour"]
                if "is_closed" in hour_data:
                    shop_hour.is_closed = hour_data["is_closed"]
                shop_hour.save()

        return ShopHours.objects.filter(shop=shop)

    @staticmethod
    def get_shop_open_days(shop_id):
        """Get list of days a shop is open"""
        shop = Shop.objects.get(id=shop_id)

        # Get all shop hours where not closed
        open_hours = ShopHours.objects.filter(shop=shop, is_closed=False)

        # Return list of weekdays
        return [h.weekday for h in open_hours]

    @staticmethod
    def is_shop_open(shop_id, date_time=None):
        """Check if shop is open at the given date and time"""
        if date_time is None:
            date_time = timezone.now()

        shop = Shop.objects.get(id=shop_id)

        # Get day of week (0 = Sunday, 6 = Saturday)
        weekday = date_time.weekday()

        # Adjust for Django's weekday (0 = Monday) vs our schema (0 = Sunday)
        if weekday == 6:  # If Sunday in Django
            weekday = 0  # It's 0 in our schema
        else:
            weekday += 1  # Otherwise add 1

        # Check if shop is open on this day
        try:
            shop_hours = ShopHours.objects.get(shop=shop, weekday=weekday)

            if shop_hours.is_closed:
                return False

            # Check if time is within opening hours
            current_time = date_time.time()
            return shop_hours.from_hour <= current_time <= shop_hours.to_hour
        except ShopHours.DoesNotExist:
            return False

    @staticmethod
    def get_next_open_time(shop_id, from_date_time=None):
        """Get the next time a shop will be open"""
        if from_date_time is None:
            from_date_time = timezone.now()

        shop = Shop.objects.get(id=shop_id)

        # Start checking from the current day
        current_date = from_date_time.date()
        current_time = from_date_time.time()

        # Check for 7 days (full week)
        for day_offset in range(7):
            check_date = current_date + timedelta(days=day_offset)

            # Get weekday (0 = Sunday, 6 = Saturday)
            weekday = check_date.weekday()

            # Adjust for Django's weekday (0 = Monday) vs our schema (0 = Sunday)
            if weekday == 6:  # If Sunday in Django
                weekday = 0  # It's 0 in our schema
            else:
                weekday += 1  # Otherwise add 1

            try:
                shop_hours = ShopHours.objects.get(shop=shop, weekday=weekday)

                # Skip if closed on this day
                if shop_hours.is_closed:
                    continue

                # If it's the current day, check if we're before closing time
                if day_offset == 0 and current_time > shop_hours.to_hour:
                    continue

                # If it's the current day and we're after opening time, return current time
                if day_offset == 0 and current_time >= shop_hours.from_hour:
                    return timezone.make_aware(datetime.combine(current_date, current_time))

                # Otherwise, return opening time for this day
                return timezone.make_aware(datetime.combine(check_date, shop_hours.from_hour))
            except ShopHours.DoesNotExist:
                continue

        # If no open days found, return None
        return None

    @staticmethod
    def get_opening_hours_text(shop_id, language=None):
        """Get formatted text representation of opening hours"""
        from django.utils.translation import get_language

        from core.localization.translator import translate_text

        current_language = language or get_language()

        shop = Shop.objects.get(id=shop_id)
        hours = ShopHours.objects.filter(shop=shop).order_by("weekday")

        if not hours.exists():
            return translate_text(
                "Opening hours not available",
                "ساعات العمل غير متوفرة" if current_language == "ar" else None,
            )

        weekday_names = {
            0: translate_text("Sunday", "الأحد" if current_language == "ar" else None),
            1: translate_text("Monday", "الاثنين" if current_language == "ar" else None),
            2: translate_text("Tuesday", "الثلاثاء" if current_language == "ar" else None),
            3: translate_text("Wednesday", "الأربعاء" if current_language == "ar" else None),
            4: translate_text("Thursday", "الخميس" if current_language == "ar" else None),
            5: translate_text("Friday", "الجمعة" if current_language == "ar" else None),
            6: translate_text("Saturday", "السبت" if current_language == "ar" else None),
        }

        closed_text = translate_text("Closed", "مغلق" if current_language == "ar" else None)

        lines = []
        for hour in hours:
            weekday = weekday_names[hour.weekday]

            if hour.is_closed:
                line = f"{weekday}: {closed_text}"
            else:
                from_time = hour.from_hour.strftime("%I:%M %p")
                to_time = hour.to_hour.strftime("%I:%M %p")
                line = f"{weekday}: {from_time} - {to_time}"

            lines.append(line)

        return "\n".join(lines)
