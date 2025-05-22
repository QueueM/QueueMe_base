import logging
import uuid
from datetime import timedelta

from django.conf import settings
from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.customersapp.models import Customer
from apps.notificationsapp.models import (
    ABTest,
    Campaign,
    CampaignRecipient,
    NotificationEvent,
)
from apps.notificationsapp.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class CampaignService:
    """
    Service for managing campaign workflows, execution, segmentation,
    and performance tracking.
    """

    @classmethod
    def create_campaign(cls, data):
        """Create a new campaign with the provided data"""
        campaign = Campaign.objects.create(
            name=data.get("name"),
            description=data.get("description", ""),
            campaign_type=data.get("campaign_type"),
            status="draft",
            target_audience=data.get("target_audience", {}),
            scheduling=data.get("scheduling", {}),
            created_by_id=data.get("created_by_id"),
        )

        # Associate templates if provided
        if data.get("email_template_id"):
            campaign.email_template_id = data.get("email_template_id")

        if data.get("sms_template_id"):
            campaign.sms_template_id = data.get("sms_template_id")

        if data.get("push_template_id"):
            campaign.push_template_id = data.get("push_template_id")

        campaign.save()
        return campaign

    @classmethod
    def update_campaign(cls, campaign_id, data):
        """Update an existing campaign with the provided data"""
        campaign = Campaign.objects.get(id=campaign_id)

        # Only allow updates to draft or scheduled campaigns
        if campaign.status not in ["draft", "scheduled"]:
            raise ValueError(f"Cannot update campaign with status '{campaign.status}'")

        # Update basic fields
        if "name" in data:
            campaign.name = data["name"]

        if "description" in data:
            campaign.description = data["description"]

        if "campaign_type" in data:
            campaign.campaign_type = data["campaign_type"]

        if "target_audience" in data:
            campaign.target_audience = data["target_audience"]

        if "scheduling" in data:
            campaign.scheduling = data["scheduling"]

        if "channels" in data:
            campaign.channels = data["channels"]

        # Update template associations
        if "email_template_id" in data:
            campaign.email_template_id = data.get("email_template_id")

        if "sms_template_id" in data:
            campaign.sms_template_id = data.get("sms_template_id")

        if "push_template_id" in data:
            campaign.push_template_id = data.get("push_template_id")

        campaign.updated_at = timezone.now()
        campaign.save()

        return campaign

    @classmethod
    def get_campaign(cls, campaign_id):
        """Get a campaign by ID with template details"""
        campaign = Campaign.objects.get(id=campaign_id)
        return campaign

    @classmethod
    def get_campaigns(cls, **filters):
        """Get campaigns matching the provided filters"""
        campaigns = Campaign.objects.all()

        if "status" in filters:
            campaigns = campaigns.filter(status=filters["status"])

        if "campaign_type" in filters:
            campaigns = campaigns.filter(campaign_type=filters["campaign_type"])

        if "created_by" in filters:
            campaigns = campaigns.filter(created_by=filters["created_by"])

        if "search" in filters and filters["search"]:
            search_term = filters["search"]
            campaigns = campaigns.filter(
                Q(name__icontains=search_term) | Q(description__icontains=search_term)
            )

        # Apply sorting
        sort_by = filters.get("sort_by", "-created_at")
        campaigns = campaigns.order_by(sort_by)

        return campaigns

    @classmethod
    def build_recipient_list(cls, campaign):
        """
        Build the list of recipients for a campaign based on segmentation criteria
        Returns the number of recipients added
        """
        # Clear existing recipients if any exist
        CampaignRecipient.objects.filter(campaign=campaign).delete()

        target_audience = campaign.target_audience or {}
        audience_type = target_audience.get("type", "all_customers")

        # Base query for customers
        customers_query = Customer.objects.filter(is_active=True)

        # Apply segmentation filters
        if audience_type == "segment":
            segments = target_audience.get("segments", [])

            # Process demographic filters
            if "demographics" in segments:
                demographics = segments["demographics"]

                if "gender" in demographics:
                    gender_filter = demographics["gender"]
                    if gender_filter and gender_filter != "all":
                        customers_query = customers_query.filter(gender=gender_filter)

                if "age_range" in demographics:
                    age_range = demographics["age_range"]
                    if "min_age" in age_range and age_range["min_age"]:
                        min_birth_date = timezone.now().date() - timedelta(
                            days=365 * int(age_range["min_age"])
                        )
                        customers_query = customers_query.filter(
                            birth_date__lte=min_birth_date
                        )

                    if "max_age" in age_range and age_range["max_age"]:
                        max_birth_date = timezone.now().date() - timedelta(
                            days=365 * int(age_range["max_age"])
                        )
                        customers_query = customers_query.filter(
                            birth_date__gte=max_birth_date
                        )

            # Process location filters
            if "location" in segments:
                location = segments["location"]

                if "cities" in location and location["cities"]:
                    customers_query = customers_query.filter(
                        city__in=location["cities"]
                    )

                if "countries" in location and location["countries"]:
                    customers_query = customers_query.filter(
                        country__in=location["countries"]
                    )

                if "regions" in location and location["regions"]:
                    customers_query = customers_query.filter(
                        region__in=location["regions"]
                    )

            # Process behavior filters
            if "behavior" in segments:
                behavior = segments["behavior"]

                if "has_booked" in behavior and behavior["has_booked"] is not None:
                    has_booked = behavior["has_booked"]
                    if has_booked:
                        customers_query = customers_query.filter(
                            bookings__isnull=False
                        ).distinct()
                    else:
                        customers_query = customers_query.filter(bookings__isnull=True)

                if "last_booking" in behavior:
                    last_booking = behavior["last_booking"]

                    if last_booking == "last_7_days":
                        date_threshold = timezone.now() - timedelta(days=7)
                        customers_query = customers_query.filter(
                            bookings__created_at__gte=date_threshold
                        ).distinct()
                    elif last_booking == "last_30_days":
                        date_threshold = timezone.now() - timedelta(days=30)
                        customers_query = customers_query.filter(
                            bookings__created_at__gte=date_threshold
                        ).distinct()
                    elif last_booking == "last_90_days":
                        date_threshold = timezone.now() - timedelta(days=90)
                        customers_query = customers_query.filter(
                            bookings__created_at__gte=date_threshold
                        ).distinct()

                if "booking_count" in behavior:
                    booking_count = behavior["booking_count"]

                    if "min" in booking_count and booking_count["min"] is not None:
                        min_count = int(booking_count["min"])
                        customers_query = customers_query.annotate(
                            num_bookings=Count("bookings")
                        ).filter(num_bookings__gte=min_count)

                    if "max" in booking_count and booking_count["max"] is not None:
                        max_count = int(booking_count["max"])
                        customers_query = customers_query.annotate(
                            num_bookings=Count("bookings")
                        ).filter(num_bookings__lte=max_count)

            # Process custom segment
            if "custom_segment" in segments and segments["custom_segment"]:
                segment_id = segments["custom_segment"]
                from apps.customersapp.services.segmentation_service import (
                    SegmentationService,
                )

                segmentation_service = SegmentationService()

                # Get customers in the custom segment
                segment_customers = segmentation_service.get_segment_customers(
                    segment_id
                )
                customers_query = customers_query.filter(id__in=segment_customers)

        elif audience_type == "specific_customers":
            # Use explicit list of customer IDs
            customer_ids = target_audience.get("customer_ids", [])
            customers_query = customers_query.filter(id__in=customer_ids)

        elif audience_type == "shop_customers":
            # Customers who have interacted with specific shops
            shop_ids = target_audience.get("shop_ids", [])
            customers_query = customers_query.filter(
                bookings__shop_id__in=shop_ids
            ).distinct()

        # Get the final list of customers
        customers = customers_query.distinct()

        # Create campaign recipients
        batch_size = 1000
        recipient_count = 0

        # Process in batches to avoid memory issues with large lists
        for i in range(0, customers.count(), batch_size):
            batch = customers[i : i + batch_size]
            recipients = []

            for customer in batch:
                # Set channels based on customer preferences
                channels = []

                # Check if notification settings exist and respect preferences
                try:
                    notification_settings = customer.get_notification_settings()

                    if (
                        "email" in campaign.channels
                        and notification_settings.email_enabled
                    ):
                        channels.append("email")

                    if "sms" in campaign.channels and notification_settings.sms_enabled:
                        channels.append("sms")

                    if (
                        "push" in campaign.channels
                        and notification_settings.push_enabled
                    ):
                        channels.append("push")
                except:
                    # If no settings found, use all campaign channels
                    channels = campaign.channels

                if not channels:
                    continue  # Skip if no valid channels

                recipient = CampaignRecipient(
                    id=uuid.uuid4(),
                    campaign=campaign,
                    customer_id=customer.id,
                    channels=channels,
                    recipient_data={
                        "first_name": customer.first_name,
                        "last_name": customer.last_name,
                        "email": customer.email,
                        "phone_number": customer.phone_number,
                    },
                )
                recipients.append(recipient)

            if recipients:
                CampaignRecipient.objects.bulk_create(recipients)
                recipient_count += len(recipients)

        # Update campaign with the count
        campaign.recipient_count = recipient_count
        campaign.save()

        return recipient_count

    @classmethod
    def schedule_campaign(cls, campaign_id, schedule_data):
        """Schedule a campaign for future delivery"""
        campaign = Campaign.objects.get(id=campaign_id)

        if campaign.status not in ["draft"]:
            raise ValueError(
                f"Cannot schedule campaign with status '{campaign.status}'"
            )

        # Set scheduling options from data
        campaign.scheduling = schedule_data
        campaign.status = "scheduled"
        campaign.save()

        # Build the recipient list
        cls.build_recipient_list(campaign)

        # If it's scheduled for immediate delivery, process it
        if schedule_data.get("send_now", False):
            cls.process_campaign(campaign)

        return campaign

    @classmethod
    def cancel_campaign(cls, campaign_id, cancel_reason=None):
        """Cancel a scheduled campaign"""
        campaign = Campaign.objects.get(id=campaign_id)

        if campaign.status not in ["scheduled", "in_progress"]:
            raise ValueError(f"Cannot cancel campaign with status '{campaign.status}'")

        campaign.status = "cancelled"
        campaign.cancellation_reason = cancel_reason
        campaign.cancelled_at = timezone.now()
        campaign.save()

        return campaign

    @classmethod
    def process_campaign(cls, campaign):
        """Process a campaign by sending notifications to recipients"""
        # Only process scheduled campaigns
        if campaign.status != "scheduled":
            if campaign.status == "draft":
                # Auto-build recipient list if needed
                cls.build_recipient_list(campaign)
                campaign.status = "scheduled"
                campaign.save()
            else:
                return False

        # Mark campaign as in progress
        campaign.status = "in_progress"
        campaign.started_at = timezone.now()
        campaign.save()

        # Check if this is an A/B test campaign
        is_ab_test = False
        abtest = None
        variant_assignment = {}

        if campaign.ab_test_id:
            abtest = ABTest.objects.filter(id=campaign.ab_test_id).first()
            if abtest and abtest.status == "active":
                is_ab_test = True

                # Prepare distribution logic for A/B test
                variant_distribution = abtest.traffic_split  # e.g., {'A': 50, 'B': 50}

                # Get recipients and assign variants
                recipients = CampaignRecipient.objects.filter(campaign=campaign)

                # Assign variants based on distribution
                import random

                variant_keys = list(variant_distribution.keys())

                for recipient in recipients:
                    # Weighted random choice based on distribution
                    weights = [variant_distribution[k] for k in variant_keys]
                    variant = random.choices(variant_keys, weights=weights, k=1)[0]
                    variant_assignment[str(recipient.id)] = variant

        # Get all recipients for the campaign
        recipients = CampaignRecipient.objects.filter(campaign=campaign)

        sent_count = 0
        failed_count = 0

        # Batch size for processing
        batch_size = getattr(settings, "CAMPAIGN_PROCESS_BATCH_SIZE", 100)

        for i in range(0, recipients.count(), batch_size):
            batch = recipients[i : i + batch_size]

            for recipient in batch:
                # Skip already processed recipients
                if recipient.status in ["sent", "failed"]:
                    if recipient.status == "sent":
                        sent_count += 1
                    else:
                        failed_count += 1
                    continue

                # Get notification templates based on A/B test variant if applicable
                email_template = None
                sms_template = None
                push_template = None

                if is_ab_test and str(recipient.id) in variant_assignment:
                    variant = variant_assignment[str(recipient.id)]
                    recipient.ab_test_variant = variant

                    if variant == "A":
                        if "email" in recipient.channels:
                            email_template = campaign.email_template
                        if "sms" in recipient.channels:
                            sms_template = campaign.sms_template
                        if "push" in recipient.channels:
                            push_template = campaign.push_template
                    else:  # Variant B
                        if "email" in recipient.channels:
                            email_template = abtest.variant_b_email_template
                        if "sms" in recipient.channels:
                            sms_template = abtest.variant_b_sms_template
                        if "push" in recipient.channels:
                            push_template = abtest.variant_b_push_template
                else:
                    # Standard campaign without A/B testing
                    if "email" in recipient.channels:
                        email_template = campaign.email_template
                    if "sms" in recipient.channels:
                        sms_template = campaign.sms_template
                    if "push" in recipient.channels:
                        push_template = campaign.push_template

                recipient_data = recipient.recipient_data or {}

                try:
                    # Send notifications through each channel
                    if "email" in recipient.channels and email_template:
                        cls._send_email_notification(
                            campaign, recipient, email_template, recipient_data
                        )

                    if "sms" in recipient.channels and sms_template:
                        cls._send_sms_notification(
                            campaign, recipient, sms_template, recipient_data
                        )

                    if "push" in recipient.channels and push_template:
                        cls._send_push_notification(
                            campaign, recipient, push_template, recipient_data
                        )

                    recipient.status = "sent"
                    recipient.sent_at = timezone.now()
                    recipient.save()
                    sent_count += 1

                except Exception as e:
                    logger.error(f"Failed to send campaign notification: {str(e)}")
                    recipient.status = "failed"
                    recipient.error_message = str(e)
                    recipient.save()
                    failed_count += 1

        # Update campaign with completion info
        campaign.sent_count = sent_count
        campaign.failed_count = failed_count

        if sent_count + failed_count >= campaign.recipient_count:
            campaign.status = "completed"
            campaign.completed_at = timezone.now()

        campaign.save()

        return {
            "sent_count": sent_count,
            "failed_count": failed_count,
            "status": campaign.status,
        }

    @classmethod
    def _send_email_notification(cls, campaign, recipient, template, recipient_data):
        """Send email notification for a campaign recipient"""
        if not template:
            raise ValueError("Email template is required")

        # Get recipient email
        email = recipient_data.get("email")
        if not email:
            raise ValueError("Recipient email is required")

        # Send notification through the notification service
        notification_id = NotificationService.send_notification(
            notification_type="campaign_email",
            recipient_id=recipient.customer_id,
            title=template.subject,
            message=None,  # Not needed for email
            channels=["email"],
            data={
                "campaign_id": str(campaign.id),
                "recipient_id": str(recipient.id),
                "template_id": str(template.id),
            },
            email_options={
                "template_id": str(template.id),
                "recipient_email": email,
                "template_data": recipient_data,
            },
        )

        # Store the notification ID for tracking
        recipient.notification_ids = recipient.notification_ids or []
        recipient.notification_ids.append(str(notification_id))
        recipient.save()

        return notification_id

    @classmethod
    def _send_sms_notification(cls, campaign, recipient, template, recipient_data):
        """Send SMS notification for a campaign recipient"""
        if not template:
            raise ValueError("SMS template is required")

        # Get recipient phone number
        phone_number = recipient_data.get("phone_number")
        if not phone_number:
            raise ValueError("Recipient phone number is required")

        # Send notification through the notification service
        notification_id = NotificationService.send_notification(
            notification_type="campaign_sms",
            recipient_id=recipient.customer_id,
            title=None,  # Not needed for SMS
            message=None,  # Will use template
            channels=["sms"],
            data={
                "campaign_id": str(campaign.id),
                "recipient_id": str(recipient.id),
                "template_id": str(template.id),
            },
            sms_options={
                "template_id": str(template.id),
                "recipient_phone": phone_number,
                "template_data": recipient_data,
            },
        )

        # Store the notification ID for tracking
        recipient.notification_ids = recipient.notification_ids or []
        recipient.notification_ids.append(str(notification_id))
        recipient.save()

        return notification_id

    @classmethod
    def _send_push_notification(cls, campaign, recipient, template, recipient_data):
        """Send push notification for a campaign recipient"""
        if not template:
            raise ValueError("Push notification template is required")

        # Send notification through the notification service
        notification_id = NotificationService.send_notification(
            notification_type="campaign_push",
            recipient_id=recipient.customer_id,
            title=template.title,
            message=template.body,
            channels=["push"],
            data={
                "campaign_id": str(campaign.id),
                "recipient_id": str(recipient.id),
                "template_id": str(template.id),
                "action_url": template.action_url,
                "action_button_text": template.action_button_text,
                "image_url": template.image_url,
            },
            template_data=recipient_data,
        )

        # Store the notification ID for tracking
        recipient.notification_ids = recipient.notification_ids or []
        recipient.notification_ids.append(str(notification_id))
        recipient.save()

        return notification_id

    @classmethod
    def get_campaign_report(cls, campaign_id):
        """Get detailed campaign performance report"""
        campaign = Campaign.objects.get(id=campaign_id)

        report = {
            "id": str(campaign.id),
            "name": campaign.name,
            "status": campaign.status,
            "campaign_type": campaign.campaign_type,
            "channels": campaign.channels,
            "recipient_count": campaign.recipient_count,
            "sent_count": campaign.sent_count,
            "failed_count": campaign.failed_count,
            "created_at": campaign.created_at,
            "scheduled_at": campaign.scheduled_at,
            "started_at": campaign.started_at,
            "completed_at": campaign.completed_at,
            "delivery_metrics": cls._get_delivery_metrics(campaign),
            "engagement_metrics": cls._get_engagement_metrics(campaign),
            "conversion_metrics": cls._get_conversion_metrics(campaign),
            "timeline": cls._get_campaign_timeline(campaign),
        }

        # Add A/B test results if this is an A/B test campaign
        if campaign.ab_test_id:
            report["ab_test_results"] = cls._get_ab_test_results(campaign)

        return report

    @classmethod
    def _get_delivery_metrics(cls, campaign):
        """Get delivery metrics for a campaign"""
        recipients = CampaignRecipient.objects.filter(campaign=campaign)

        # Calculate delivery rate
        delivered = recipients.filter(status="sent").count()
        total = recipients.count()
        delivery_rate = (delivered / total * 100) if total > 0 else 0

        # Calculate metrics by channel
        email_sent = recipients.filter(
            status="sent", channels__contains=["email"]
        ).count()
        sms_sent = recipients.filter(status="sent", channels__contains=["sms"]).count()
        push_sent = recipients.filter(
            status="sent", channels__contains=["push"]
        ).count()

        # Calculate bounces and failures
        bounces = NotificationEvent.objects.filter(
            notification__data__campaign_id=str(campaign.id), event_type="bounce"
        ).count()

        failures = recipients.filter(status="failed").count()

        return {
            "delivery_rate": round(delivery_rate, 2),
            "delivered": delivered,
            "total": total,
            "by_channel": {
                "email": email_sent,
                "sms": sms_sent,
                "push": push_sent,
            },
            "bounces": bounces,
            "failures": failures,
        }

    @classmethod
    def _get_engagement_metrics(cls, campaign):
        """Get engagement metrics for a campaign"""
        # Get notification IDs associated with this campaign
        recipient_notification_ids = [
            notification_id
            for recipient in CampaignRecipient.objects.filter(campaign=campaign)
            for notification_id in (recipient.notification_ids or [])
        ]

        # Get events for these notifications
        if not recipient_notification_ids:
            return {
                "open_rate": 0,
                "click_rate": 0,
                "opens": 0,
                "clicks": 0,
                "unsubscribes": 0,
            }

        events = NotificationEvent.objects.filter(
            notification_id__in=recipient_notification_ids
        )

        # Calculate metrics
        opens = events.filter(event_type="open").count()
        clicks = events.filter(event_type="click").count()
        unsubscribes = events.filter(event_type="unsubscribe").count()

        total_delivered = CampaignRecipient.objects.filter(
            campaign=campaign, status="sent"
        ).count()
        open_rate = (opens / total_delivered * 100) if total_delivered > 0 else 0
        click_rate = (clicks / total_delivered * 100) if total_delivered > 0 else 0

        # Calculate engagement by channel
        email_opens = events.filter(event_type="open", channel="email").count()
        email_clicks = events.filter(event_type="click", channel="email").count()

        push_opens = events.filter(event_type="open", channel="push").count()
        push_clicks = events.filter(event_type="click", channel="push").count()

        return {
            "open_rate": round(open_rate, 2),
            "click_rate": round(click_rate, 2),
            "opens": opens,
            "clicks": clicks,
            "unsubscribes": unsubscribes,
            "by_channel": {
                "email": {"opens": email_opens, "clicks": email_clicks},
                "push": {"opens": push_opens, "clicks": push_clicks},
            },
        }

    @classmethod
    def _get_conversion_metrics(cls, campaign):
        """Get conversion metrics for a campaign"""
        # Metrics depend on campaign type/goal
        campaign_type = campaign.campaign_type

        # Get recipient IDs
        recipient_ids = CampaignRecipient.objects.filter(
            campaign=campaign, status="sent"
        ).values_list("customer_id", flat=True)

        # Define time window for attributing conversions
        attribution_window = timedelta(days=7)  # Default 7 days
        start_time = campaign.started_at or campaign.created_at
        end_time = start_time + attribution_window

        if campaign_type == "booking_reminder":
            # Track bookings created after campaign
            from apps.bookingapp.models import Booking

            bookings = Booking.objects.filter(
                user_id__in=recipient_ids,
                created_at__gte=start_time,
                created_at__lte=end_time,
            )

            booking_count = bookings.count()
            booking_value = bookings.aggregate(Sum("price"))["price__sum"] or 0

            return {
                "booking_count": booking_count,
                "booking_value": booking_value,
                "conversion_rate": round(
                    (booking_count / len(recipient_ids) * 100) if recipient_ids else 0,
                    2,
                ),
            }

        elif campaign_type == "promotional":
            # Track shop visits and eventual bookings
            from apps.bookingapp.models import Booking
            from apps.shopapp.models import ShopVisit

            shop_visits = ShopVisit.objects.filter(
                customer_id__in=recipient_ids,
                visited_at__gte=start_time,
                visited_at__lte=end_time,
            )

            bookings = Booking.objects.filter(
                user_id__in=recipient_ids,
                created_at__gte=start_time,
                created_at__lte=end_time,
            )

            visit_count = shop_visits.count()
            booking_count = bookings.count()

            return {
                "shop_visit_count": visit_count,
                "booking_count": booking_count,
                "visit_rate": round(
                    (visit_count / len(recipient_ids) * 100) if recipient_ids else 0, 2
                ),
                "booking_rate": round(
                    (booking_count / len(recipient_ids) * 100) if recipient_ids else 0,
                    2,
                ),
            }

        else:
            # Generic conversion metrics
            return {
                "engagement_count": NotificationEvent.objects.filter(
                    notification__data__campaign_id=str(campaign.id),
                    event_type__in=["open", "click"],
                ).count()
            }

    @classmethod
    def _get_campaign_timeline(cls, campaign):
        """Get timeline of campaign events"""
        timeline = []

        # Add campaign creation
        timeline.append(
            {
                "event": "created",
                "timestamp": campaign.created_at,
                "details": f"Campaign created by {campaign.created_by.email if campaign.created_by else 'system'}",
            }
        )

        # Add scheduling event if scheduled
        if campaign.scheduled_at:
            timeline.append(
                {
                    "event": "scheduled",
                    "timestamp": campaign.scheduled_at,
                    "details": f"Campaign scheduled for delivery",
                }
            )

        # Add start event if started
        if campaign.started_at:
            timeline.append(
                {
                    "event": "started",
                    "timestamp": campaign.started_at,
                    "details": f"Campaign delivery started",
                }
            )

        # Add completion event if completed
        if campaign.completed_at:
            timeline.append(
                {
                    "event": "completed",
                    "timestamp": campaign.completed_at,
                    "details": f"Campaign delivery completed ({campaign.sent_count} sent, {campaign.failed_count} failed)",
                }
            )

        # Add cancellation event if cancelled
        if campaign.status == "cancelled" and campaign.cancelled_at:
            timeline.append(
                {
                    "event": "cancelled",
                    "timestamp": campaign.cancelled_at,
                    "details": f"Campaign cancelled{': ' + campaign.cancellation_reason if campaign.cancellation_reason else ''}",
                }
            )

        # Sort timeline by timestamp
        timeline.sort(key=lambda x: x["timestamp"])

        return timeline

    @classmethod
    def _get_ab_test_results(cls, campaign):
        """Get results for A/B test campaign"""
        if not campaign.ab_test_id:
            return None

        abtest = ABTest.objects.get(id=campaign.ab_test_id)

        # Get recipients by variant
        variant_a_recipients = CampaignRecipient.objects.filter(
            campaign=campaign, ab_test_variant="A", status="sent"
        )

        variant_b_recipients = CampaignRecipient.objects.filter(
            campaign=campaign, ab_test_variant="B", status="sent"
        )

        # Get notification IDs by variant
        variant_a_notification_ids = [
            notification_id
            for recipient in variant_a_recipients
            for notification_id in (recipient.notification_ids or [])
        ]

        variant_b_notification_ids = [
            notification_id
            for recipient in variant_b_recipients
            for notification_id in (recipient.notification_ids or [])
        ]

        # Get events for these variants
        variant_a_events = NotificationEvent.objects.filter(
            notification_id__in=variant_a_notification_ids
        )
        variant_b_events = NotificationEvent.objects.filter(
            notification_id__in=variant_b_notification_ids
        )

        # Calculate metrics for variant A
        a_count = variant_a_recipients.count()
        a_opens = variant_a_events.filter(event_type="open").count()
        a_clicks = variant_a_events.filter(event_type="click").count()

        a_open_rate = (a_opens / a_count * 100) if a_count > 0 else 0
        a_click_rate = (a_clicks / a_count * 100) if a_count > 0 else 0

        # Calculate metrics for variant B
        b_count = variant_b_recipients.count()
        b_opens = variant_b_events.filter(event_type="open").count()
        b_clicks = variant_b_events.filter(event_type="click").count()

        b_open_rate = (b_opens / b_count * 100) if b_count > 0 else 0
        b_click_rate = (b_clicks / b_count * 100) if b_count > 0 else 0

        # Determine winner based on success metric
        winner = None
        confidence = 0

        if abtest.success_metric == "open_rate":
            if a_open_rate > b_open_rate:
                winner = "A"
                confidence = (
                    min(100, (a_open_rate - b_open_rate) / b_open_rate * 100)
                    if b_open_rate > 0
                    else 100
                )
            elif b_open_rate > a_open_rate:
                winner = "B"
                confidence = (
                    min(100, (b_open_rate - a_open_rate) / a_open_rate * 100)
                    if a_open_rate > 0
                    else 100
                )
        elif abtest.success_metric == "click_rate":
            if a_click_rate > b_click_rate:
                winner = "A"
                confidence = (
                    min(100, (a_click_rate - b_click_rate) / b_click_rate * 100)
                    if b_click_rate > 0
                    else 100
                )
            elif b_click_rate > a_click_rate:
                winner = "B"
                confidence = (
                    min(100, (b_click_rate - a_click_rate) / a_click_rate * 100)
                    if a_click_rate > 0
                    else 100
                )

        # Only set winner if confidence meets threshold and test is complete
        has_winner = winner and confidence >= (abtest.minimum_confidence or 95)

        # Update test status and winner if test is complete and we have a winner
        if campaign.status == "completed" and has_winner and abtest.status == "active":
            abtest.winner = winner
            abtest.confidence = confidence
            abtest.status = "completed"
            abtest.completed_at = timezone.now()
            abtest.save()

        return {
            "test_name": abtest.name,
            "test_id": str(abtest.id),
            "variants": {
                "A": {
                    "recipient_count": a_count,
                    "open_count": a_opens,
                    "click_count": a_clicks,
                    "open_rate": round(a_open_rate, 2),
                    "click_rate": round(a_click_rate, 2),
                },
                "B": {
                    "recipient_count": b_count,
                    "open_count": b_opens,
                    "click_count": b_clicks,
                    "open_rate": round(b_open_rate, 2),
                    "click_rate": round(b_click_rate, 2),
                },
            },
            "success_metric": abtest.success_metric,
            "winner": winner,
            "confidence": round(confidence, 2),
            "has_significant_winner": has_winner,
            "status": abtest.status,
        }
