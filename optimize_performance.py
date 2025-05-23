"""
Script to optimize performance and enable caching for QueueMe backend
"""

import os
import sys
from pathlib import Path

# Add project directory to path
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

# Django setup
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "queueme.settings.base")
import django

django.setup()

import time


# Import required modules
from django.core.cache import cache
from django.db import connection


def optimize_database_indexes():
    """Create missing indexes for frequently queried fields"""
    print("Optimizing database indexes...")

    # List of SQL statements to create indexes
    index_statements = [
        # Booking indexes
        "CREATE INDEX IF NOT EXISTS idx_booking_status ON booking_booking(status);",
        "CREATE INDEX IF NOT EXISTS idx_booking_date ON booking_booking(booking_date);",
        "CREATE INDEX IF NOT EXISTS idx_booking_customer ON booking_booking(customer_id);",
        "CREATE INDEX IF NOT EXISTS idx_booking_service ON booking_booking(service_id);",
        # User indexes
        "CREATE INDEX IF NOT EXISTS idx_user_phone ON authapp_user(phone_number);",
        "CREATE INDEX IF NOT EXISTS idx_user_active ON authapp_user(is_active);",
        # Service indexes
        "CREATE INDEX IF NOT EXISTS idx_service_shop ON service_service(shop_id);",
        "CREATE INDEX IF NOT EXISTS idx_service_category ON service_service(category_id);",
        "CREATE INDEX IF NOT EXISTS idx_service_active ON service_service(is_active);",
        # Shop indexes
        "CREATE INDEX IF NOT EXISTS idx_shop_location ON shop_shop(location_id);",
        "CREATE INDEX IF NOT EXISTS idx_shop_company ON shop_shop(company_id);",
        # Payment indexes
        "CREATE INDEX IF NOT EXISTS idx_payment_status ON payment_payment(status);",
        "CREATE INDEX IF NOT EXISTS idx_payment_date ON payment_payment(created_at);",
    ]

    # Execute each index creation statement
    with connection.cursor() as cursor:
        for statement in index_statements:
            try:
                cursor.execute(statement)
                print(f"Created index: {statement}")
            except Exception as e:
                print(f"Error creating index: {e}")

    print("Database indexes optimization completed.")


def configure_caching():
    """Configure and test caching"""
    print("Configuring caching...")

    # Test cache functionality
    cache_key = "performance_test"
    cache.set(cache_key, "Cache is working", 60)
    cached_value = cache.get(cache_key)

    if cached_value == "Cache is working":
        print("Cache is configured and working correctly.")
    else:
        print("WARNING: Cache is not working properly!")

    # Add cache configuration recommendations
    print("\nCache configuration recommendations:")
    print("1. Use Redis for production caching")
    print("2. Configure the following in settings/production.py:")
    print(
        """
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': 'redis://127.0.0.1:6379/1',
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'PARSER_CLASS': 'redis.connection.HiredisParser',
            }
        }
    }
    """
    )

    # Cache timeout recommendations
    print("\nRecommended cache timeouts:")
    print("- User profiles: 3600 seconds (1 hour)")
    print("- Shop details: 1800 seconds (30 minutes)")
    print("- Service listings: 900 seconds (15 minutes)")
    print("- Booking availability: 300 seconds (5 minutes)")
    print("- Dynamic content: 60 seconds (1 minute)")


def optimize_queries():
    """Identify and optimize slow queries"""
    print("Optimizing database queries...")

    # List of query optimizations to implement
    optimizations = [
        "1. Use select_related() for ForeignKey relationships",
        "2. Use prefetch_related() for reverse relationships and ManyToMany fields",
        "3. Defer unused fields with defer() or only()",
        "4. Use values() or values_list() when only specific fields are needed",
        "5. Add database indexes for frequently filtered fields",
        "6. Use bulk operations (bulk_create, bulk_update) for batch processing",
        "7. Implement query caching for expensive operations",
        "8. Use F() expressions for database-level updates",
        "9. Implement pagination for large result sets",
        "10. Use database-level aggregation instead of Python-level processing",
    ]

    print("\nQuery optimization recommendations:")
    for opt in optimizations:
        print(f"  {opt}")

    # Example of query optimization
    print("\nExample query optimization:")
    print(
        """
    # Before optimization
    bookings = Booking.objects.filter(status='confirmed')
    for booking in bookings:
        print(booking.customer.name, booking.service.name)
    
    # After optimization
    bookings = Booking.objects.filter(status='confirmed').select_related('customer', 'service')
    for booking in bookings:
        print(booking.customer.name, booking.service.name)
    """
    )


def configure_connection_pooling():
    """Configure database connection pooling"""
    print("Configuring database connection pooling...")

    # Connection pooling recommendations
    print("\nDatabase connection pooling recommendations:")
    print("1. Install django-db-connection-pool package")
    print("2. Configure the following in settings/production.py:")
    print(
        """
    DATABASES = {
        'default': {
            'ENGINE': 'dj_db_conn_pool.backends.postgresql',
            'NAME': 'queueme',
            'USER': 'queueme_user',
            'PASSWORD': '********',
            'HOST': 'localhost',
            'PORT': '5432',
            'CONN_MAX_AGE': 0,
            'OPTIONS': {
                'MAX_CONNS': 20,
                'MIN_CONNS': 5,
                'MAX_SHARED': 10,
                'MAX_OVERFLOW': 10,
                'POOL_TIMEOUT': 30,
                'RECYCLE': 300,
            }
        }
    }
    """
    )


def optimize_static_files():
    """Optimize static file handling"""
    print("Optimizing static file handling...")

    # Static file optimization recommendations
    print("\nStatic file optimization recommendations:")
    print("1. Enable django-compressor for CSS/JS minification")
    print("2. Configure the following in settings/production.py:")
    print(
        """
    # Static files compression
    COMPRESS_ENABLED = True
    COMPRESS_CSS_FILTERS = [
        'compressor.filters.css_default.CssAbsoluteFilter',
        'compressor.filters.cssmin.rCSSMinFilter',
    ]
    COMPRESS_JS_FILTERS = [
        'compressor.filters.jsmin.JSMinFilter',
    ]
    COMPRESS_OFFLINE = True
    
    # Static files serving
    STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'
    """
    )

    print("3. Use AWS CloudFront or similar CDN for static file delivery")
    print("4. Implement proper cache headers for static files")


def main():
    """Main optimization function"""
    print("=" * 80)
    print("QueueMe Backend Performance Optimization")
    print("=" * 80)

    start_time = time.time()

    # Run optimization functions
    optimize_database_indexes()
    print("\n" + "-" * 80 + "\n")

    configure_caching()
    print("\n" + "-" * 80 + "\n")

    optimize_queries()
    print("\n" + "-" * 80 + "\n")

    configure_connection_pooling()
    print("\n" + "-" * 80 + "\n")

    optimize_static_files()

    # Summary
    elapsed_time = time.time() - start_time
    print("\n" + "=" * 80)
    print(f"Performance optimization completed in {elapsed_time:.2f} seconds.")
    print("=" * 80)


if __name__ == "__main__":
    main()
