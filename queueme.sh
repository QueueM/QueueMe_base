#!/bin/bash

# Queue Me Project Setup Script
# This script creates the initial project structure for Queue Me

set -e

echo "Creating Queue Me project structure..."

# Create root directory
mkdir -p queueme_backend
cd queueme_backend

# Create top-level files
touch .gitignore
touch .env.example
touch docker-compose.yml
touch docker-compose.prod.yml
touch docker-entrypoint.sh
touch Dockerfile
touch Dockerfile.celery
touch manage.py
touch pyproject.toml
touch README.md
touch requirements.txt
touch setup.cfg
touch setup.py
touch pytest.ini
touch tox.ini
touch .flake8
touch .isort.cfg
touch .pre-commit-config.yaml

# Make entrypoint script executable
chmod +x docker-entrypoint.sh

# Create directory structure
mkdir -p .github/workflows
mkdir -p requirements
mkdir -p queueme/settings
mkdir -p algorithms/{availability,geo,ml,optimization,ranking,search,security}
mkdir -p apps
mkdir -p core/{cache,exceptions,localization,storage,tasks,utils}
mkdir -p api/v1/views
mkdir -p api/documentation
mkdir -p websockets/{consumers,middleware}
mkdir -p config/{nginx,redis,supervisor}
mkdir -p db/init
mkdir -p docker
mkdir -p docs/{algorithms,api,architecture}
mkdir -p locale/{ar,en}/LC_MESSAGES
mkdir -p scripts/db_migration
mkdir -p static/{css,img,js}
mkdir -p templates/{email,errors}
mkdir -p tests/{integration,performance,security}
mkdir -p utils/sms/backends

# Create apps subdirectories
apps_list=(
    "authapp"
    "bookingapp"
    "categoriesapp"
    "chatapp"
    "companiesapp"
    "customersapp"
    "discountapp"
    "employeeapp"
    "followapp"
    "geoapp"
    "notificationsapp"
    "packageapp"
    "payment"
    "queueapp"
    "reelsapp"
    "reportanalyticsapp"
    "reviewapp"
    "rolesapp"
    "serviceapp"
    "shopapp"
    "shopDashboardApp"
    "specialistsapp"
    "storiesapp"
    "subscriptionapp"
)

for app in "${apps_list[@]}"; do
    mkdir -p apps/$app/{migrations,services,tests}
    touch apps/$app/__init__.py
    touch apps/$app/admin.py
    touch apps/$app/apps.py
    touch apps/$app/models.py
    touch apps/$app/serializers.py
    touch apps/$app/urls.py
    touch apps/$app/views.py
    touch apps/$app/migrations/__init__.py
    touch apps/$app/tests/__init__.py
done

# Create requirements files
touch requirements/{base.txt,development.txt,production.txt,test.txt}

# Create basic __init__.py files
find . -type d -not -path "*/\.*" -exec sh -c 'if [ ! -f "$1/__init__.py" ]; then touch "$1/__init__.py"; fi' _ {} \;

echo "Queue Me project structure created successfully!"
