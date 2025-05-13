#!/bin/bash

# Wait for database to be ready
echo "Waiting for database..."
while ! nc -z $POSTGRES_HOST $POSTGRES_PORT; do
  sleep 0.1
done
echo "Database is ready!"

# Apply database migrations
echo "Applying migrations..."
python manage.py migrate

# Create superuser if not exists
echo "Creating superuser if not exists..."
python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'queueme.settings.production')
django.setup()
from apps.authapp.models import User
if not User.objects.filter(phone_number='$DJANGO_SUPERUSER_PHONE').exists():
    User.objects.create_superuser('$DJANGO_SUPERUSER_PHONE', '$DJANGO_SUPERUSER_PASSWORD')
    print('Superuser created.')
else:
    print('Superuser already exists.')
"

# Create initial roles and permissions
echo "Setting up initial roles and permissions..."
python manage.py loaddata initial_roles.json
python manage.py loaddata initial_permissions.json

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Execute command
exec "$@"
