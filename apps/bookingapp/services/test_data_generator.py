"""
Test data generator for bookings
"""
import random
from datetime import datetime, timedelta

from django.utils import timezone

from apps.bookingapp.models import Booking, BookingStatus


def generate_test_bookings(count=5, days_range=7):
    """
    Generate test bookings for demonstration purposes

    Args:
        count (int): Number of bookings to generate
        days_range (int): Range of days to generate bookings for

    Returns:
        list: List of created booking objects
    """
    # Sample data
    customer_names = [
        "John Doe",
        "Jane Smith",
        "Michael Johnson",
        "Emily Davis",
        "Robert Wilson",
        "Sarah Martinez",
        "David Anderson",
        "Lisa Thomas",
        "James Jackson",
        "Jennifer White",
        "Charles Harris",
        "Mary Martin",
        "Daniel Thompson",
        "Patricia Garcia",
        "Matthew Rodriguez",
        "Linda Lewis",
    ]

    customer_emails = [
        "john.doe@example.com",
        "jane.smith@example.com",
        "michael.j@example.com",
        "emily.davis@example.com",
        "rwilson@example.com",
        "smartinez@example.com",
        "david.a@example.com",
        "lisa.thomas@example.com",
        "jamesjackson@example.com",
        "jennifer.w@example.com",
        "charris@example.com",
        "mary.martin@example.com",
        "daniel.t@example.com",
        "pgarcia@example.com",
        "matt.rod@example.com",
        "linda.lewis@example.com",
    ]

    customer_phones = [
        "+1234567890",
        "+1987654321",
        "+1555123456",
        "+1555789012",
        "+1555234567",
        "+1555345678",
        "+1555456789",
        "+1555567890",
        "+1555678901",
        "+1555789012",
        "+1555890123",
        "+1555901234",
        "+1555012345",
        "+1555123456",
        "+1555234567",
        "+1555345678",
    ]

    services = [
        "Haircut",
        "Manicure",
        "Massage",
        "Facial",
        "Hair Coloring",
        "Pedicure",
        "Waxing",
        "Spa Treatment",
        "Hair Styling",
        "Makeup",
        "Consultation",
        "Hair Extension",
        "Skin Treatment",
        "Body Scrub",
    ]

    specialists = [
        "Dr. Smith",
        "Dr. Johnson",
        "Therapist Williams",
        "Stylist Brown",
        "Technician Davis",
        "Specialist Wilson",
        "Consultant Moore",
        "Expert Taylor",
        "Professional Anderson",
        "Practitioner Thomas",
        "Beautician Jackson",
        "Therapist Harris",
    ]

    notes = [
        "Client requested extra attention to detail",
        "First-time customer, special discount applied",
        "Regular client with specific preferences",
        "Allergic to certain products, check notes",
        "VIP client, provide premium service",
        "Referred by another client",
        "Sensitive skin, use gentle products",
        "Previous service had issues, needs special care",
        "Celebrating special occasion",
        "Requested specific specialist",
        "Called to confirm appointment",
        "May arrive late, confirmed via phone",
        "Bringing a friend who might book services",
        "Requested specific product to be used",
        "Has mobility issues, needs assistance",
    ]

    # Get or create booking statuses
    statuses = list(BookingStatus.objects.all())
    if not statuses:
        # Create default statuses if none exist
        statuses = [
            BookingStatus.objects.create(name="Pending", color="#FFA500", is_active=True),
            BookingStatus.objects.create(name="Confirmed", color="#008000", is_active=True),
            BookingStatus.objects.create(name="Completed", color="#0000FF", is_active=True),
            BookingStatus.objects.create(name="Cancelled", color="#FF0000", is_active=True),
            BookingStatus.objects.create(name="No-show", color="#800080", is_active=True),
        ]

    # Generate bookings
    created_bookings = []
    now = timezone.now()

    for _ in range(count):
        # Generate random date within the specified range
        days_offset = random.randint(-days_range, days_range)
        booking_date = (now + timedelta(days=days_offset)).date()

        # Generate random time
        hour = random.randint(9, 17)  # 9 AM to 5 PM
        minute = random.choice([0, 15, 30, 45])
        booking_time = datetime.time(hour=hour, minute=minute)

        # Create booking
        booking = Booking.objects.create(
            customer_name=random.choice(customer_names),
            customer_email=random.choice(customer_emails),
            customer_phone=random.choice(customer_phones),
            service=random.choice(services),
            specialist=random.choice(specialists),
            booking_date=booking_date,
            booking_time=booking_time,
            duration=random.choice([30, 45, 60, 90, 120]),  # Duration in minutes
            status=random.choice(statuses),
            price=random.randint(50, 500),
            notes=random.choice(notes) if random.random() > 0.3 else "",
        )

        created_bookings.append(booking)

    return created_bookings
