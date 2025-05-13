# QueueMe Development Guide

This guide provides instructions for setting up and working with the QueueMe platform codebase during development.

## Project Overview

QueueMe is a Django-based queue and appointment management system that supports multiple domains:

- **queueme.net**: Main site
- **shop.queueme.net**: Shop interface
- **admin.queueme.net**: Admin panel
- **api.queueme.net**: API endpoints with documentation

## 1. Development Environment Setup

### Prerequisites

- Python 3.9+
- PostgreSQL 12+
- Redis 6+
- Git

### System Dependencies

Some packages require system libraries to function properly:

```bash
# On macOS with Homebrew
brew install libmagic  # Required for python-magic (content moderation functionality)

# On Debian/Ubuntu
sudo apt-get install libmagic1  # Required for python-magic

# On CentOS/RHEL
sudo yum install file-devel  # Required for python-magic
```

### Virtual Environment Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/queueme.git
cd queueme

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements/development.txt
```

### Environment Variables

Create a `.env` file in the project root with the following variables:

```
# Django settings
DEBUG=True
SECRET_KEY=your-secret-key-for-development-only
ALLOWED_HOSTS=localhost,127.0.0.1,.queueme.local

# Database settings
POSTGRES_DB=QueueMe_DB
POSTGRES_USER=arise
POSTGRES_PASSWORD=Arisearise@1
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# Redis settings
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_URL=redis://localhost:6379/1

# Email settings - use a development backend
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

### Database Setup

```bash
# Create the database
createdb queueme

# Apply migrations
python manage.py migrate

# Create a superuser
python manage.py createsuperuser

# Load initial data (if available)
python manage.py loaddata fixtures/initial_data.json
```

## 2. Local Domain Setup

To work with the multi-domain setup locally, you need to configure your hosts file:

### Unix/macOS

```bash
sudo nano /etc/hosts
```

Add these lines:

```
127.0.0.1  queueme.local
127.0.0.1  shop.queueme.local
127.0.0.1  admin.queueme.local
127.0.0.1  api.queueme.local
```

### Windows

Edit `C:\Windows\System32\drivers\etc\hosts` as Administrator and add the same lines.

## 3. Running the Development Server

### Start All Required Services

```bash
# Start PostgreSQL (if not started as a service)
pg_ctl -D /path/to/your/postgres/data -l logfile start

# Start Redis
redis-server

# Start Django development server
python manage.py runserver 0.0.0.0:8000

# In a new terminal, start Daphne for WebSockets
python manage.py runworker websocket

# In a new terminal, start Celery worker (if using Celery)
celery -A queueme worker --loglevel=info

# In a new terminal, start Celery beat (if using scheduled tasks)
celery -A queueme beat --loglevel=info
```

### Access Local Domains

You can now access the application at:

- Main site: http://queueme.local:8000
- Shop interface: http://shop.queueme.local:8000
- Admin panel: http://admin.queueme.local:8000
- API: http://api.queueme.local:8000

## 4. Code Quality and Standards

### Code Style Guidelines

We follow PEP 8 standards with some customizations. Here's how to maintain code quality:

```bash
# Sort imports
isort .

# Format code with Black
black .

# Check for style issues
flake8
```

### Pre-commit Hooks

We recommend using pre-commit hooks to automate code quality checks:

```bash
# Install pre-commit
pip install pre-commit

# Install the git hooks
pre-commit install

# Run against all files
pre-commit run --all-files
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=.

# Run specific tests
pytest apps/queueapp/tests/test_services.py
```

## 5. Project Structure

```
queueme/
├── api/                # API versioning and docs
├── apps/               # Django applications
│   ├── authapp/        # Authentication
│   ├── queueapp/       # Queue management
│   ├── shopapp/        # Shop management
│   └── ...             # Other domain-specific apps
├── config/             # Configuration files
│   ├── nginx/          # Nginx configurations
│   └── systemd/        # Systemd service files
├── core/               # Core functionality
├── queueme/            # Project settings
│   ├── middleware/     # Custom middleware
│   ├── settings/       # Environment-specific settings
│   └── urls.py         # Main URL configuration
├── scripts/            # Utility scripts
├── static/             # Static files
├── templates/          # HTML templates
└── utils/              # Shared utilities
```

## 6. Django App Development

When creating a new app, follow these conventions:

1. Create the app in the `apps` directory
2. Use a clear, descriptive name ending with "app" (e.g., `reviewapp`)
3. Organize the app with these subdirectories:
   - `models.py`: Database models
   - `services/`: Business logic in service classes
   - `serializers.py`: API serializers
   - `views.py`: API views and viewsets
   - `urls.py`: URL routing
   - `signals.py`: Django signals
   - `tests/`: Test files

## 7. API Development

### API Documentation

We use Swagger/OpenAPI for API documentation:

1. Add proper docstrings to your API views and viewsets
2. Use drf-yasg decorators for complex parameters
3. View the documentation at `/api/docs/swagger/`

### Versioning

- Use the `/api/` prefix for all API endpoints
- Add version prefix for significant changes (e.g., `/api/v2/`)

## 8. WebSocket Development

WebSocket consumers are in each app's `consumers.py` file:

1. Inherit from `AsyncWebsocketConsumer`
2. Implement `connect()`, `disconnect()`, and `receive()` methods
3. Add authentication and error handling

## 9. Common Development Tasks

### Adding a New Domain

1. Update the `ALLOWED_HOSTS` setting
2. Add to your local `/etc/hosts` file
3. Create a new Nginx configuration in `config/nginx/`
4. Update the domain routing in `queueme/middleware/domain_routing.py`

### Adding a New API Endpoint

1. Create view function or viewset in the appropriate app
2. Add URL pattern to the app's `urls.py`
3. Add to main URL patterns in `queueme/urls.py`
4. Add tests in the app's `tests/` directory

## 10. Troubleshooting

### Common Issues

1. **Domain access issues**: Make sure your hosts file is updated and you're using the right port
2. **WebSocket connection failures**: Check if Daphne is running and configured correctly
3. **Database connection errors**: Verify PostgreSQL is running and credentials are correct
4. **Redis errors**: Ensure Redis is running and accessible

### Debug Tools

- Django Debug Toolbar (available in development mode)
- Django Logging (see `logs/queueme.log`)
- Django Extensions shell_plus: `python manage.py shell_plus`

## 11. Deployment

See `DEPLOYMENT_CHECKLIST.md` for production deployment instructions.

---

For additional help, contact the development team or refer to internal documentation.
