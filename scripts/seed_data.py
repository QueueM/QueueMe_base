#!/usr/bin/env python
# =============================================================================
# Queue Me Data Seeding Script
# Sophisticated test data generation for development and testing environments
# =============================================================================

import argparse
import logging
import os
import random
import sys
import uuid
from datetime import datetime, time, timedelta

import django
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from faker import Faker
from tqdm import tqdm

from apps.authapp.models import User
from apps.bookingapp.models import Appointment
from apps.categoriesapp.models import Category
from apps.chatapp.models import Conversation, Message
from apps.companiesapp.models import Company
from apps.employeeapp.models import Employee
from apps.followapp.models import Follow
from apps.notificationsapp.models import NotificationTemplate
from apps.payment.models import Transaction
from apps.queueapp.models import Queue, QueueTicket
from apps.reelsapp.models import Reel
from apps.reviewapp.models import Review
from apps.rolesapp.models import Permission, Role, UserRole
from apps.serviceapp.models import Service, ServiceAvailability
from apps.shopapp.models import Shop, ShopHours
from apps.specialistsapp.models import Specialist, SpecialistService, SpecialistWorkingHours
from apps.storiesapp.models import Story

# Setup Django environment
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "queueme.settings.development")
django.setup()


# Import Django models


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(BASE_DIR, "seed_data.log")),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Initialize Faker with Arabic and English locales
fake = Faker(["ar_SA", "en_US"])

# Saudi Arabia cities
SAUDI_CITIES = [
    {"name": "Riyadh", "ar_name": "الرياض", "lat": 24.7136, "lng": 46.6753},
    {"name": "Jeddah", "ar_name": "جدة", "lat": 21.4858, "lng": 39.1925},
    {"name": "Mecca", "ar_name": "مكة المكرمة", "lat": 21.3891, "lng": 39.8579},
    {"name": "Medina", "ar_name": "المدينة المنورة", "lat": 24.5247, "lng": 39.5692},
    {"name": "Dammam", "ar_name": "الدمام", "lat": 26.4207, "lng": 50.0888},
    {"name": "Khobar", "ar_name": "الخبر", "lat": 26.2172, "lng": 50.1971},
    {"name": "Jubail", "ar_name": "الجبيل", "lat": 27.0046, "lng": 49.6616},
    {"name": "Tabuk", "ar_name": "تبوك", "lat": 28.3998, "lng": 36.5715},
    {"name": "Abha", "ar_name": "أبها", "lat": 18.2164, "lng": 42.5053},
    {"name": "Taif", "ar_name": "الطائف", "lat": 21.2700, "lng": 40.4158},
]


class DataSeeder:
    def __init__(self, scale_factor=1, clear_existing=False):
        """Initialize the seeder with scale factor"""
        self.scale_factor = scale_factor
        self.clear_existing = clear_existing

        # Define entity counts based on scale factor
        self.counts = {
            "users": int(50 * scale_factor),
            "companies": int(5 * scale_factor),
            "shops_per_company": int(3 * scale_factor),
            "categories": int(10 * scale_factor),
            "subcategories_per_category": int(5 * scale_factor),
            "employees_per_shop": int(5 * scale_factor),
            "services_per_shop": int(8 * scale_factor),
            "appointments_per_shop": int(20 * scale_factor),
            "queue_tickets_per_shop": int(15 * scale_factor),
            "reviews_per_shop": int(10 * scale_factor),
            "reels_per_shop": int(5 * scale_factor),
            "stories_per_shop": int(3 * scale_factor),
            "conversations_per_shop": int(5 * scale_factor),
            "messages_per_conversation": int(10 * scale_factor),
        }

        # Store created entities for reference
        self.users = []
        self.companies = []
        self.shops = []
        self.categories = []
        self.subcategories = []
        self.employees = []
        self.specialists = []
        self.services = []
        self.roles = []
        self.locations = []

        # Queues for batch operations
        self.queue_operations = []

    def clear_data(self):
        """Clear existing data from database"""
        logger.info("Clearing existing data...")

        # Delete in reverse dependency order
        Message.objects.all().delete()
        Conversation.objects.all().delete()
        Review.objects.all().delete()
        Story.objects.all().delete()
        Reel.objects.all().delete()
        QueueTicket.objects.all().delete()
        Queue.objects.all().delete()
        Appointment.objects.all().delete()
        Transaction.objects.all().delete()
        Follow.objects.all().delete()
        SpecialistService.objects.all().delete()
        SpecialistWorkingHours.objects.all().delete()
        Specialist.objects.all().delete()
        ServiceAvailability.objects.all().delete()
        Service.objects.all().delete()
        ShopHours.objects.all().delete()
        Employee.objects.all().delete()
        UserRole.objects.all().delete()
        Shop.objects.all().delete()
        Company.objects.all().delete()
        Category.objects.all().delete()
        Location.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()

        logger.info("Data cleared successfully")

    def create_base_data(self):
        """Create base data needed for other entities"""
        logger.info("Creating base data...")

        # Create cities/locations
        for city in SAUDI_CITIES:
            location = Location.objects.create(
                country="Saudi Arabia",
                city=city["name"],
                city_ar=city["ar_name"],
                latitude=city["lat"],
                longitude=city["lng"],
                address=fake.street_address(),
                address_ar=fake.street_address(),
            )
            self.locations.append(location)

        # Create base roles if they don't exist
        self.roles = self._create_roles()

        logger.info("Base data created successfully")

    def _create_roles(self):
        """Create default roles and permissions"""
        # Create permissions if they don't exist
        permissions = []
        resources = [
            "shop",
            "service",
            "employee",
            "specialist",
            "customer",
            "booking",
            "queue",
            "report",
            "reel",
            "story",
            "chat",
            "payment",
            "subscription",
            "discount",
            "review",
            "package",
            "category",
        ]
        actions = ["view", "add", "edit", "delete"]

        for resource in resources:
            for action in actions:
                perm, created = Permission.objects.get_or_create(resource=resource, action=action)
                permissions.append(perm)

        # Create roles with appropriate permissions
        roles = []

        # QueueMe Admin role (full access)
        admin_role, created = Role.objects.get_or_create(
            name="Queue Me Administrator",
            role_type="queue_me_admin",
            description="Full administrative access to all Queue Me platform features",
        )
        admin_role.permissions.set(permissions)
        roles.append(admin_role)

        # QueueMe Employee roles
        cs_role, created = Role.objects.get_or_create(
            name="Queue Me Customer Support",
            role_type="queue_me_employee",
            description="Customer support role with access to help businesses and customers",
        )
        cs_permissions = Permission.objects.filter(
            resource__in=["shop", "customer", "booking", "review"],
            action__in=["view", "edit"],
        )
        cs_role.permissions.set(cs_permissions)
        roles.append(cs_role)

        # Company role
        company_role, created = Role.objects.get_or_create(
            name="Company Manager",
            role_type="company",
            description="Company-level access to manage all shops",
        )
        company_permissions = Permission.objects.exclude(
            resource__in=["subscription", "category"], action="delete"
        )
        company_role.permissions.set(company_permissions)
        roles.append(company_role)

        # Shop Manager role
        shop_manager_role, created = Role.objects.get_or_create(
            name="Shop Manager",
            role_type="shop_manager",
            description="Shop manager with access to manage shop operations",
        )
        shop_permissions = Permission.objects.exclude(
            resource__in=["subscription", "category"], action="delete"
        ).exclude(resource__in=["customer"], action="delete")
        shop_manager_role.permissions.set(shop_permissions)
        roles.append(shop_manager_role)

        # Specialist role
        specialist_role, created = Role.objects.get_or_create(
            name="Specialist",
            role_type="shop_employee",
            description="Specialist providing services",
        )
        specialist_permissions = Permission.objects.filter(
            resource__in=["booking", "queue", "chat"], action__in=["view", "edit"]
        )
        specialist_role.permissions.set(specialist_permissions)
        roles.append(specialist_role)

        # Customer Service role
        cs_shop_role, created = Role.objects.get_or_create(
            name="Customer Service",
            role_type="shop_employee",
            description="Handle customer inquiries and bookings",
        )
        cs_shop_permissions = Permission.objects.filter(
            resource__in=["booking", "queue", "customer", "chat", "review"],
            action__in=["view", "add", "edit"],
        )
        cs_shop_role.permissions.set(cs_shop_permissions)
        roles.append(cs_shop_role)

        return roles

    def seed_users(self):
        """Create customer users"""
        logger.info(f"Creating {self.counts['users']} users...")

        batch_size = 100
        user_batches = []

        for i in tqdm(range(self.counts["users"])):
            # 70% Arabic names, 30% English names to represent Saudi Arabia demographics
            if random.random() < 0.7:
                fake.seed_instance(i)  # For reproducibility
                phone = f"+9665{fake.numerify('########')}"  # Saudi mobile format
                name = fake.name_male() if random.random() < 0.5 else fake.name_female()
                email = fake.email()
                lang = "ar"
            else:
                fake.seed_instance(i + 10000)  # Different seed for English names
                phone = f"+9665{fake.numerify('########')}"
                name = fake.name()
                email = fake.email()
                lang = "en"

            user = User(
                phone_number=phone,
                email=email,
                user_type="customer",
                is_verified=True,
                profile_completed=True,
                date_joined=fake.date_time_between(
                    start_date="-1y",
                    end_date="now",
                    tzinfo=timezone.get_current_timezone(),
                ),
            )
            user_batches.append(user)

            # Create user profile in the associated app
            # We'll add this later in a separate batch operation
            self.queue_operations.append(
                {
                    "type": "customer_profile",
                    "user": user,
                    "name": name,
                    "language": lang,
                    "location": random.choice(self.locations),
                }
            )

            # Batch create
            if len(user_batches) >= batch_size or i == self.counts["users"] - 1:
                User.objects.bulk_create(user_batches)
                self.users.extend(user_batches)
                user_batches = []

        logger.info(f"Created {len(self.users)} users")

    def seed_companies(self):
        """Create companies and their shops"""
        logger.info(f"Creating {self.counts['companies']} companies with shops...")

        for i in range(self.counts["companies"]):
            # Create company
            company_name = fake.company()
            company_owner = User.objects.create(
                phone_number=f"+9665{fake.numerify('########')}",
                email=fake.company_email(),
                user_type="employee",
                is_verified=True,
                profile_completed=True,
            )

            company = Company.objects.create(
                name=company_name,
                registration_number=fake.numerify("######"),
                owner=company_owner,
                contact_email=fake.company_email(),
                contact_phone=f"+9665{fake.numerify('########')}",
                description=fake.paragraph(),
                location=random.choice(self.locations),
                is_active=True,
            )
            self.companies.append(company)

            # Assign company role to owner
            company_role = Role.objects.get(role_type="company")
            UserRole.objects.create(user=company_owner, role=company_role)

            # Create shops for this company
            for j in range(self.counts["shops_per_company"]):
                shop_location = random.choice(self.locations)
                shop_name = f"{company_name} - {shop_location.city}"
                shop_username = f"{company_name.lower().replace(' ', '')}{j+1}"

                # Create shop manager
                manager = User.objects.create(
                    phone_number=f"+9665{fake.numerify('########')}",
                    email=fake.email(),
                    user_type="employee",
                    is_verified=True,
                    profile_completed=True,
                )

                # Create shop
                shop = Shop.objects.create(
                    company=company,
                    name=shop_name,
                    description=fake.paragraph(),
                    location=shop_location,
                    phone_number=f"+9665{fake.numerify('########')}",
                    email=fake.company_email(),
                    manager=manager,
                    is_verified=random.random() < 0.7,  # 70% are verified
                    verification_date=timezone.now() if random.random() < 0.7 else None,
                    is_active=True,
                    username=shop_username,
                )
                self.shops.append(shop)

                # Assign shop manager role
                shop_manager_role = Role.objects.get(role_type="shop_manager")
                shop_role = shop_manager_role  # Use existing instance or create shop-specific role
                UserRole.objects.create(user=manager, role=shop_role)

                # Create shop hours
                for weekday in range(7):
                    is_closed = weekday == 5  # Closed on Friday

                    if not is_closed:
                        # Random opening hours between 7-10 AM
                        open_hour = random.randint(7, 10)
                        # Random closing hours between 7-10 PM
                        close_hour = random.randint(19, 22)

                        ShopHours.objects.create(
                            shop=shop,
                            weekday=weekday,
                            from_hour=time(open_hour, 0),
                            to_hour=time(close_hour, 0),
                            is_closed=is_closed,
                        )
                    else:
                        ShopHours.objects.create(
                            shop=shop,
                            weekday=weekday,
                            from_hour=time(9, 0),
                            to_hour=time(17, 0),
                            is_closed=is_closed,
                        )

                # Create a queue for this shop
                Queue.objects.create(
                    shop=shop, name=f"{shop_name} Queue", status="open", max_capacity=50
                )

        logger.info(f"Created {len(self.companies)} companies and {len(self.shops)} shops")

    def seed_categories(self):
        """Create service categories"""
        logger.info(f"Creating {self.counts['categories']} parent categories...")

        # Main categories
        category_names = [
            {"en": "Beauty & Spa", "ar": "الجمال والسبا"},
            {"en": "Hair Salons", "ar": "صالونات الشعر"},
            {"en": "Barber Shops", "ar": "محلات الحلاقة"},
            {"en": "Nail Salons", "ar": "صالونات الأظافر"},
            {"en": "Massage & Relaxation", "ar": "التدليك والاسترخاء"},
            {"en": "Medical Services", "ar": "الخدمات الطبية"},
            {"en": "Fitness & Wellness", "ar": "اللياقة والعافية"},
            {"en": "Home Services", "ar": "خدمات المنزل"},
            {"en": "Auto Services", "ar": "خدمات السيارات"},
            {"en": "Professional Services", "ar": "الخدمات المهنية"},
            {"en": "Education & Training", "ar": "التعليم والتدريب"},
            {"en": "Events & Entertainment", "ar": "الفعاليات والترفيه"},
            {"en": "Food & Dining", "ar": "الطعام والمطاعم"},
            {"en": "Retail", "ar": "التجزئة"},
            {"en": "Travel & Tourism", "ar": "السفر والسياحة"},
        ]

        # Select categories based on count
        selected_categories = category_names[: min(self.counts["categories"], len(category_names))]

        for cat_data in selected_categories:
            category = Category.objects.create(
                name=cat_data["en"],
                name_ar=cat_data["ar"],
                description=fake.paragraph(),
                description_ar=fake.paragraph(),
                is_active=True,
            )
            self.categories.append(category)

            # Create subcategories
            subcategory_count = self.counts["subcategories_per_category"]

            for j in range(subcategory_count):
                if cat_data["en"] == "Beauty & Spa":
                    subcat_names = [
                        {"en": "Facial Treatments", "ar": "علاجات الوجه"},
                        {"en": "Body Treatments", "ar": "علاجات الجسم"},
                        {"en": "Makeup Services", "ar": "خدمات المكياج"},
                        {"en": "Waxing", "ar": "إزالة الشعر بالشمع"},
                        {"en": "Eyelash Extensions", "ar": "تمديد الرموش"},
                    ]
                elif cat_data["en"] == "Hair Salons":
                    subcat_names = [
                        {"en": "Haircuts", "ar": "قص الشعر"},
                        {"en": "Hair Coloring", "ar": "صبغ الشعر"},
                        {"en": "Hair Styling", "ar": "تصفيف الشعر"},
                        {"en": "Hair Treatments", "ar": "علاجات الشعر"},
                        {"en": "Hair Extensions", "ar": "إضافات الشعر"},
                    ]
                else:
                    # Generate random subcategories
                    subcat_en = f"{cat_data['en']} - {chr(65+j)}"
                    subcat_ar = f"{cat_data['ar']} - {j+1}"
                    subcat_names = [{"en": subcat_en, "ar": subcat_ar}]

                if j < len(subcat_names):
                    subcat_data = subcat_names[j]
                    subcategory = Category.objects.create(
                        parent=category,
                        name=subcat_data["en"],
                        name_ar=subcat_data["ar"],
                        description=fake.paragraph(),
                        description_ar=fake.paragraph(),
                        is_active=True,
                    )
                    self.subcategories.append(subcategory)

        logger.info(
            f"Created {len(self.categories)} parent categories and {len(self.subcategories)} subcategories"
        )

    def seed_employees_and_specialists(self):
        """Create employees and specialists for shops"""
        logger.info(f"Creating employees and specialists for {len(self.shops)} shops...")

        for shop in self.shops:
            # Get role IDs
            specialist_role = Role.objects.get(name="Specialist")
            cs_role = Role.objects.get(name="Customer Service")

            # Create employees
            for i in range(self.counts["employees_per_shop"]):
                # Create employee user
                employee_user = User.objects.create(
                    phone_number=f"+9665{fake.numerify('########')}",
                    email=fake.email(),
                    user_type="employee",
                    is_verified=True,
                    profile_completed=True,
                )

                # Create employee record
                first_name = fake.first_name()
                last_name = fake.last_name()

                employee = Employee.objects.create(
                    user=employee_user,
                    shop=shop,
                    first_name=first_name,
                    last_name=last_name,
                    position=random.choice(
                        ["specialist", "receptionist", "customer service", "manager"]
                    ),
                    is_active=True,
                )
                self.employees.append(employee)

                # Assign appropriate role
                if employee.position == "specialist":
                    UserRole.objects.create(user=employee_user, role=specialist_role)

                    # Create specialist profile for this employee
                    specialist = Specialist.objects.create(
                        employee=employee,
                        bio=fake.paragraph(),
                        experience_years=random.randint(1, 15),
                        is_verified=shop.is_verified,  # Same as shop verification
                    )
                    self.specialists.append(specialist)

                    # Create working hours for specialist
                    for weekday in range(7):
                        # Get shop hours
                        shop_hour = ShopHours.objects.filter(shop=shop, weekday=weekday).first()

                        if shop_hour and not shop_hour.is_closed:
                            # Specialist hours are within shop hours
                            from_hour = shop_hour.from_hour
                            to_hour = shop_hour.to_hour

                            # Sometimes specialists have shorter hours
                            if random.random() < 0.3:
                                # Add 1-2 hours to start time
                                from_hour_int = from_hour.hour + random.randint(1, 2)
                                from_hour = time(min(from_hour_int, 23), 0)

                                # Subtract 1-2 hours from end time
                                to_hour_int = to_hour.hour - random.randint(1, 2)
                                to_hour = time(max(to_hour_int, from_hour_int + 1), 0)

                            SpecialistWorkingHours.objects.create(
                                specialist=specialist,
                                weekday=weekday,
                                from_hour=from_hour,
                                to_hour=to_hour,
                                is_off=False,
                            )
                        else:
                            # Day off or shop closed
                            SpecialistWorkingHours.objects.create(
                                specialist=specialist,
                                weekday=weekday,
                                from_hour=time(9, 0),
                                to_hour=time(17, 0),
                                is_off=True,
                            )
                else:
                    # Assign customer service role to non-specialists
                    UserRole.objects.create(user=employee_user, role=cs_role)

        logger.info(
            f"Created {len(self.employees)} employees including {len(self.specialists)} specialists"
        )

    def seed_services(self):
        """Create services for each shop"""
        logger.info(f"Creating services for {len(self.shops)} shops...")

        for shop in self.shops:
            # Get specialists for this shop
            shop_specialists = [s for s in self.specialists if s.employee.shop == shop]

            if not shop_specialists:
                continue

            # Get subcategories relevant to this shop's location (for local relevance)
            relevant_subcategories = self.subcategories

            for i in range(self.counts["services_per_shop"]):
                # Create service
                price = random.randint(50, 500)  # SAR
                duration = random.choice([15, 30, 45, 60, 90, 120])  # minutes
                slot_granularity = min(duration, 30)  # Max 30 min slots
                buffer_before = random.choice([0, 5, 10, 15])
                buffer_after = random.choice([0, 5, 10, 15])

                service = Service.objects.create(
                    shop=shop,
                    category=random.choice(relevant_subcategories),
                    name=fake.sentence(nb_words=3).rstrip("."),
                    description=fake.paragraph(),
                    price=price,
                    duration=duration,
                    slot_granularity=slot_granularity,
                    buffer_before=buffer_before,
                    buffer_after=buffer_after,
                    service_location=random.choice(["in_shop", "in_home", "both"]),
                    is_active=True,
                )
                self.services.append(service)

                # Create service availability (same as shop hours by default)
                shop_hours = ShopHours.objects.filter(shop=shop)

                for shop_hour in shop_hours:
                    if not shop_hour.is_closed:
                        ServiceAvailability.objects.create(
                            service=service,
                            weekday=shop_hour.weekday,
                            from_hour=shop_hour.from_hour,
                            to_hour=shop_hour.to_hour,
                            is_closed=False,
                        )
                    else:
                        ServiceAvailability.objects.create(
                            service=service,
                            weekday=shop_hour.weekday,
                            from_hour=time(9, 0),
                            to_hour=time(17, 0),
                            is_closed=True,
                        )

                # Assign specialists to service
                specialist_count = min(len(shop_specialists), random.randint(1, 3))
                assigned_specialists = random.sample(shop_specialists, specialist_count)

                for specialist in assigned_specialists:
                    SpecialistService.objects.create(
                        specialist=specialist,
                        service=service,
                        is_primary=(specialist == assigned_specialists[0]),  # First one is primary
                    )

        logger.info(f"Created {len(self.services)} services")

    def seed_appointments(self):
        """Create appointments for services"""
        logger.info("Creating appointments for services...")

        total_appointments = 0

        for shop in self.shops:
            # Get services for this shop
            shop_services = [s for s in self.services if s.shop == shop]

            if not shop_services:
                continue

            # Create appointments for each service
            for i in range(self.counts["appointments_per_shop"]):
                service = random.choice(shop_services)

                # Get specialists for this service
                specialist_services = SpecialistService.objects.filter(service=service)

                if not specialist_services.exists():
                    continue

                specialist = random.choice(specialist_services).specialist

                # Get random customer
                customer = random.choice(self.users)

                # Generate random date within last month or next month
                days_offset = random.randint(-30, 30)
                appointment_date = timezone.now().date() + timedelta(days=days_offset)

                # Get shop hours for this date
                weekday = appointment_date.weekday()
                if weekday == 6:  # Convert Sunday (Python's 6) to our 0
                    weekday = 0
                else:
                    weekday += 1

                shop_hour = ShopHours.objects.filter(shop=shop, weekday=weekday).first()

                if not shop_hour or shop_hour.is_closed:
                    continue

                # Generate random time within shop hours
                open_hour = shop_hour.from_hour.hour
                close_hour = shop_hour.to_hour.hour - 1  # Ensure appointment ends before closing

                if close_hour <= open_hour:
                    continue

                start_hour = random.randint(open_hour, close_hour)
                start_minute = random.choice([0, 15, 30, 45])

                # Create appointment datetime
                start_datetime = timezone.make_aware(
                    datetime.combine(appointment_date, time(start_hour, start_minute))
                )

                end_datetime = start_datetime + timedelta(minutes=service.duration)

                # Determine status based on date
                if appointment_date < timezone.now().date():
                    status = random.choice(["completed", "no_show", "cancelled"])
                elif appointment_date == timezone.now().date():
                    if start_datetime < timezone.now():
                        status = random.choice(["completed", "in_progress"])
                    else:
                        status = "scheduled"
                else:
                    status = "scheduled"

                # Create appointment
                appointment = Appointment.objects.create(
                    customer=customer,
                    service=service,
                    specialist=specialist,
                    shop=shop,
                    start_time=start_datetime,
                    end_time=end_datetime,
                    status=status,
                    notes=fake.sentence() if random.random() < 0.3 else "",
                    payment_status=(
                        "paid" if status in ["completed", "in_progress"] else "pending"
                    ),
                )

                total_appointments += 1

        logger.info(f"Created {total_appointments} appointments")

    def seed_queue_tickets(self):
        """Create queue tickets for shops"""
        logger.info("Creating queue tickets for shops...")

        total_tickets = 0

        for shop in self.shops:
            # Get the queue for this shop
            queue = Queue.objects.filter(shop=shop).first()

            if not queue:
                continue

            # Get services for this shop
            shop_services = [s for s in self.services if s.shop == shop]

            if not shop_services:
                continue

            # Create queue tickets
            for i in range(self.counts["queue_tickets_per_shop"]):
                service = random.choice(shop_services)

                # Get specialists for this service
                specialist_services = SpecialistService.objects.filter(service=service)

                if specialist_services.exists():
                    specialist = random.choice(specialist_services).specialist
                else:
                    specialist = None

                # Get random customer
                customer = random.choice(self.users)

                # Generate ticket number
                ticket_number = f"Q-{fake.numerify('######')}"

                # Random status - weight towards completed for historical data
                status_weights = {
                    "waiting": 0.2,
                    "called": 0.1,
                    "serving": 0.1,
                    "served": 0.5,
                    "skipped": 0.05,
                    "cancelled": 0.05,
                }
                status = random.choices(list(status_weights.keys()), list(status_weights.values()))[
                    0
                ]

                # Position for waiting tickets
                if status == "waiting":
                    position = random.randint(1, 10)
                else:
                    position = 0

                # Times for different statuses
                now = timezone.now()
                join_time = now - timedelta(hours=random.randint(0, 12))

                if status in ["called", "serving", "served", "skipped"]:
                    called_time = join_time + timedelta(minutes=random.randint(5, 60))
                else:
                    called_time = None

                if status in ["serving", "served"]:
                    serve_time = called_time + timedelta(minutes=random.randint(1, 10))
                else:
                    serve_time = None

                if status == "served":
                    complete_time = serve_time + timedelta(minutes=random.randint(15, 60))
                    actual_wait_time = int((serve_time - join_time).total_seconds() / 60)
                else:
                    complete_time = None
                    actual_wait_time = None

                # Create queue ticket
                ticket = QueueTicket.objects.create(
                    queue=queue,
                    ticket_number=ticket_number,
                    customer=customer,
                    service=service,
                    specialist=specialist,
                    status=status,
                    position=position,
                    estimated_wait_time=random.randint(5, 60),
                    actual_wait_time=actual_wait_time,
                    notes=fake.sentence() if random.random() < 0.2 else "",
                    join_time=join_time,
                    called_time=called_time,
                    serve_time=serve_time,
                    complete_time=complete_time,
                )

                total_tickets += 1

        logger.info(f"Created {total_tickets} queue tickets")

    def seed_reviews(self):
        """Create reviews for shops, specialists, and services"""
        logger.info("Creating reviews...")

        total_reviews = 0

        for shop in self.shops:
            # Create reviews for the shop
            for i in range(self.counts["reviews_per_shop"]):
                # Get random customer
                customer = random.choice(self.users)

                # Generate star rating with weights towards higher ratings
                star_weights = {1: 0.05, 2: 0.1, 3: 0.2, 4: 0.3, 5: 0.35}
                stars = random.choices(list(star_weights.keys()), list(star_weights.values()))[0]

                # Review content based on rating
                if stars >= 4:
                    title = random.choice(
                        [
                            "Great experience",
                            "Excellent service",
                            "Highly recommended",
                            "Very satisfied",
                            "Will come back",
                        ]
                    )
                    comment = fake.paragraph()
                elif stars == 3:
                    title = random.choice(
                        [
                            "Good service",
                            "Decent experience",
                            "Satisfactory",
                            "Average service",
                            "OK experience",
                        ]
                    )
                    comment = fake.paragraph()
                else:
                    title = random.choice(
                        [
                            "Disappointing",
                            "Poor service",
                            "Needs improvement",
                            "Not satisfied",
                            "Would not recommend",
                        ]
                    )
                    comment = fake.paragraph()

                # Create shop review
                review_date = fake.date_time_between(
                    start_date="-6m",
                    end_date="now",
                    tzinfo=timezone.get_current_timezone(),
                )

                shop_review = Review.objects.create(
                    shop=shop,
                    customer=customer,
                    title=title,
                    comment=comment,
                    stars=stars,
                    created_at=review_date,
                )

                total_reviews += 1

                # Sometimes also review a specialist from this shop
                if random.random() < 0.5:
                    specialists = Specialist.objects.filter(employee__shop=shop)

                    if specialists.exists():
                        specialist = random.choice(specialists)

                        # Similar rating but with some variation
                        specialist_stars = max(1, min(5, stars + random.randint(-1, 1)))

                        Review.objects.create(
                            shop=shop,
                            specialist=specialist,
                            customer=customer,
                            title=f"Review for {specialist.employee.first_name}",
                            comment=fake.paragraph(),
                            stars=specialist_stars,
                            created_at=review_date,
                        )

                        total_reviews += 1

                # Sometimes also review a service from this shop
                if random.random() < 0.4:
                    services = Service.objects.filter(shop=shop)

                    if services.exists():
                        service = random.choice(services)

                        # Similar rating but with some variation
                        service_stars = max(1, min(5, stars + random.randint(-1, 1)))

                        Review.objects.create(
                            shop=shop,
                            service=service,
                            customer=customer,
                            title=f"Review for {service.name}",
                            comment=fake.paragraph(),
                            stars=service_stars,
                            created_at=review_date,
                        )

                        total_reviews += 1

        logger.info(f"Created {total_reviews} reviews")

    def seed_content(self):
        """Create reels and stories for shops"""
        logger.info("Creating content (reels and stories) for shops...")

        total_reels = 0
        total_stories = 0

        for shop in self.shops:
            # Create reels
            for i in range(self.counts["reels_per_shop"]):
                # Get random service from this shop
                services = Service.objects.filter(shop=shop)

                if services.exists():
                    service = random.choice(services)
                else:
                    service = None

                # Create reel
                caption = fake.sentence()
                created_at = fake.date_time_between(
                    start_date="-3m",
                    end_date="now",
                    tzinfo=timezone.get_current_timezone(),
                )

                reel = Reel.objects.create(
                    shop=shop,
                    caption=caption,
                    media_type="video",  # Assuming 'video' as most reels are videos
                    # Mock URL
                    media_url=f"https://{settings.AWS_S3_CUSTOM_DOMAIN}/mock/reels/{uuid.uuid4()}.mp4",
                    # Mock URL
                    thumbnail_url=f"https://{settings.AWS_S3_CUSTOM_DOMAIN}/mock/thumbnails/{uuid.uuid4()}.jpg",
                    likes_count=random.randint(0, 100),
                    comments_count=random.randint(0, 20),
                    shares_count=random.randint(0, 10),
                    created_at=created_at,
                )

                # Link to service
                if service:
                    reel.services.add(service)

                total_reels += 1

            # Create stories
            for i in range(self.counts["stories_per_shop"]):
                # Create story
                caption = fake.sentence() if random.random() < 0.5 else ""
                created_at = fake.date_time_between(
                    start_date="-24h",
                    end_date="now",
                    tzinfo=timezone.get_current_timezone(),
                )

                story = Story.objects.create(
                    shop=shop,
                    caption=caption,
                    media_type=random.choice(["image", "video"]),
                    # Mock URL
                    media_url=f"https://{settings.AWS_S3_CUSTOM_DOMAIN}/mock/stories/{uuid.uuid4()}.jpg",
                    created_at=created_at,
                    expires_at=created_at + timedelta(hours=24),  # 24-hour expiry
                )

                total_stories += 1

        logger.info(f"Created {total_reels} reels and {total_stories} stories")

    def seed_conversations(self):
        """Create conversations and messages between customers and shops"""
        logger.info("Creating conversations and messages...")

        total_conversations = 0
        total_messages = 0

        for shop in self.shops:
            # Create conversations
            for i in range(self.counts["conversations_per_shop"]):
                # Get random customer
                customer = random.choice(self.users)

                # Create conversation
                conversation = Conversation.objects.create(
                    customer=customer,
                    shop=shop,
                    created_at=fake.date_time_between(
                        start_date="-3m",
                        end_date="now",
                        tzinfo=timezone.get_current_timezone(),
                    ),
                    is_active=True,
                )

                total_conversations += 1

                # Get employees who can chat (customer service or shop manager)
                employees = Employee.objects.filter(shop=shop)

                if not employees.exists():
                    continue

                shop_responders = [
                    e for e in employees if e.position in ["customer service", "manager"]
                ]

                if not shop_responders:
                    shop_responders = [employees.first()]

                # Create messages for this conversation
                message_count = self.counts["messages_per_conversation"]
                for j in range(message_count):
                    # Alternate between customer and shop
                    if j % 2 == 0:
                        # Customer message
                        sender = customer
                        content = fake.sentence()
                        employee = None
                    else:
                        # Shop message
                        sender = shop_responders[0].user
                        content = fake.sentence()
                        employee = random.choice(shop_responders)

                    # Create message
                    created_at = conversation.created_at + timedelta(
                        minutes=j * 5
                    )  # 5 minutes between messages

                    message = Message.objects.create(
                        conversation=conversation,
                        sender=sender,
                        employee=employee,
                        content=content,
                        message_type="text",
                        is_read=True,
                        read_at=(
                            created_at + timedelta(minutes=1)
                            if created_at < timezone.now()
                            else None
                        ),
                        created_at=created_at,
                    )

                    total_messages += 1

        logger.info(f"Created {total_conversations} conversations with {total_messages} messages")

    def seed_follows(self):
        """Create follow relationships between customers and shops"""
        logger.info("Creating follow relationships...")

        total_follows = 0

        for user in self.users:
            # Each user follows some random shops
            follow_count = random.randint(1, 5)
            shops_to_follow = random.sample(self.shops, min(follow_count, len(self.shops)))

            for shop in shops_to_follow:
                Follow.objects.create(
                    user=user,
                    shop=shop,
                    created_at=fake.date_time_between(
                        start_date="-1y",
                        end_date="now",
                        tzinfo=timezone.get_current_timezone(),
                    ),
                )

                total_follows += 1

        logger.info(f"Created {total_follows} follow relationships")

    def seed_notification_templates(self):
        """Create notification templates"""
        logger.info("Creating notification templates...")

        templates = [
            {
                "type": "appointment_confirmation",
                "channel": "sms",
                "subject": "Appointment Confirmation",
                "body_en": "Your appointment for {{service_name}} at {{shop_name}} on {{date}} at {{time}} has been confirmed.",
                "body_ar": "تم تأكيد موعدك لـ {{service_name}} في {{shop_name}} يوم {{date}} الساعة {{time}}.",
                "variables": ["service_name", "shop_name", "date", "time"],
            },
            {
                "type": "appointment_reminder",
                "channel": "sms",
                "subject": "Appointment Reminder",
                "body_en": "Reminder: Your appointment at {{shop_name}} is tomorrow at {{time}}.",
                "body_ar": "تذكير: موعدك في {{shop_name}} غدًا الساعة {{time}}.",
                "variables": ["shop_name", "time"],
            },
            {
                "type": "queue_join_confirmation",
                "channel": "sms",
                "subject": "Queue Confirmation",
                "body_en": "You have joined the queue at {{shop_name}}. Your position is {{position}} with approximately {{estimated_wait}} minutes wait time.",
                "body_ar": "لقد انضممت إلى قائمة الانتظار في {{shop_name}}. موقعك هو {{position}} مع وقت انتظار تقريبي {{estimated_wait}} دقيقة.",
                "variables": ["shop_name", "position", "estimated_wait"],
            },
            {
                "type": "queue_called",
                "channel": "sms",
                "subject": "Your Turn",
                "body_en": "It's your turn now at {{shop_name}}. Please proceed to the counter.",
                "body_ar": "حان دورك الآن في {{shop_name}}. يرجى التوجه إلى الكاونتر.",
                "variables": ["shop_name"],
            },
        ]

        for template_data in templates:
            NotificationTemplate.objects.get_or_create(
                type=template_data["type"],
                channel=template_data["channel"],
                defaults={
                    "subject": template_data["subject"],
                    "body_en": template_data["body_en"],
                    "body_ar": template_data["body_ar"],
                    "variables": template_data["variables"],
                },
            )

        logger.info("Created notification templates")

    @transaction.atomic
    def run(self):
        """Run the complete data seeding process"""
        logger.info(f"Starting data seeding process with scale factor {self.scale_factor}...")

        start_time = datetime.now()

        if self.clear_existing:
            self.clear_data()

        self.create_base_data()
        self.seed_users()
        self.seed_companies()
        self.seed_categories()
        self.seed_employees_and_specialists()
        self.seed_services()
        self.seed_appointments()
        self.seed_queue_tickets()
        self.seed_reviews()
        self.seed_content()
        self.seed_conversations()
        self.seed_follows()
        self.seed_notification_templates()

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info(f"Data seeding completed in {duration:.2f} seconds!")


def main():
    parser = argparse.ArgumentParser(description="Seed data for Queue Me platform.")
    parser.add_argument(
        "--scale",
        type=float,
        default=1.0,
        help="Scale factor for data volume (default: 1.0)",
    )
    parser.add_argument("--clear", action="store_true", help="Clear existing data before seeding")
    args = parser.parse_args()

    seeder = DataSeeder(scale_factor=args.scale, clear_existing=args.clear)
    seeder.run()


if __name__ == "__main__":
    main()
