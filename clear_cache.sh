#!/bin/bash
# clear_cache.sh - Utility script to clear Django cache

echo "🧹 Clearing QueueMe cache..."

# Activate virtual environment if needed
# source venv/bin/activate

# Clear all cache
python manage.py shell -c "from django.core.cache import cache; cache.clear()"

# Alternatively, clear by patterns (uncomment if needed)
# python manage.py shell -c "from django.core.cache import cache; cache.delete_pattern('specialist_appointments_*'); cache.delete_pattern('customer_appointments_*')"

echo "✅ Cache cleared successfully!"
