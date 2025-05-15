# QueueMe Platform

QueueMe is an advanced queue and appointment management platform designed for businesses to manage their customer flow efficiently. The platform provides robust features for booking appointments, managing queues, and enhancing customer experience.

## Features

- **Appointment Booking**: Customers can book appointments with specialists
- **Queue Management**: Real-time queue tracking and management
- **Multi-service Scheduling**: Book multiple services in one appointment
- **Staff Management**: Manage employees, specialists, and their schedules
- **Rating and Reviews**: Collect and display customer feedback
- **Analytics Dashboard**: Track business performance and customer metrics
- **Mobile Notifications**: Send real-time updates to customers
- **WebSocket Support**: Real-time queue status and notifications
- **Multi-language Support**: Internationalization for global use
- **Scalable Architecture**: Can handle from small shops to large enterprises

## Technology Stack

- **Backend**: Django, Django REST Framework, Channels (WebSockets)
- **Database**: PostgreSQL, PostGIS (for geo-spatial features)
- **Caching**: Redis
- **Task Queue**: Celery
- **Storage**: Amazon S3 (optional)
- **Deployment**: Docker, Nginx, Gunicorn

## Project Structure

The project is organized into multiple Django apps, each serving a specific purpose:

```
queueme/                  # Project settings and configuration
  ├── settings/            # Environment-specific settings
  ├── middleware/          # Custom middleware (auth, perf, etc.)
  └── urls.py              # Main URL configuration
api/                      # API documentation and utilities
apps/                     # Django applications
  ├── authapp/             # Authentication and user management
  ├── bookingapp/          # Appointment booking
  ├── queueapp/            # Queue management
  ├── serviceapp/          # Services management
  ├── shopapp/             # Shop management
  ├── specialistsapp/      # Specialists management
  └── ...                  # Other feature-specific apps
algorithms/               # Specialized algorithms
  ├── optimization/        # Scheduling optimization
  ├── geo/                 # Geo-spatial algorithms
  └── ml/                  # Machine learning features
websockets/               # WebSocket consumers
scripts/                  # Deployment and maintenance scripts
```

## Setup and Installation

### Prerequisites

- Python 3.9+
- PostgreSQL 13+ with PostGIS extension
- Redis
- Node.js and NPM (for frontend, if applicable)

### Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/QueueM/queueme_backend.git
   cd queueme_backend
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file based on `.env.example`:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. Set up the database:
   ```bash
   python manage.py migrate
   ```

6. Create a superuser:
   ```bash
   python manage.py createsuperuser
   ```

7. Run the development server:
   ```bash
   python manage.py runserver
   ```

### Docker Setup

1. Make sure Docker and Docker Compose are installed
2. Build and start the containers:
   ```bash
   docker-compose up -d
   ```

## Deployment

For production deployment, follow these steps:

1. Set environment variables for production (see `.env.example`)
2. Use the deployment script:
   ```bash
   ./scripts/deploy.sh
   ```

For detailed deployment instructions, see [DEPLOYMENT.md](DEPLOYMENT.md).

### Security Notes

- All credentials and sensitive data must be provided via environment variables
- Set `DEBUG=False` in production
- Enable HTTPS by setting `SECURE_SSL_REDIRECT=True`
- Keep the database and media backups
- Set up rate limiting to prevent abuse
- Regularly update dependencies

## API Documentation

API documentation is available at `/api/docs/` when the server is running. It provides:

- Interactive API explorer via Swagger UI
- Detailed endpoint documentation
- Request and response examples
- Authentication instructions

## Development Guidelines

- Follow PEP 8 code style
- Write tests for new features
- Use pre-commit hooks for code quality
- Document APIs using docstrings and OpenAPI schemas
- Keep the README and documentation up to date

## License

This software is proprietary and owned by QueueMe. All rights reserved.

## Contact

For support or inquiries, contact support@queueme.net

## Recent Improvements

### Database Enhancements

- **PostgreSQL Integration**: Full support for PostgreSQL with optimized configuration
- **Migration Tools**: Comprehensive SQLite to PostgreSQL migration script with validation and resumable processing
- **Database Indexing**: Strategic indexes on queue tables for optimal performance
- **Connection Pooling**: Ready for production with connection pooling configuration

### Performance Optimizations

- **Tiered Caching**: Multi-level cache system distributing content across memory, Redis, and specialized backends
- **Query Monitoring**: Performance middleware automatically detects and logs slow queries
- **Resource Usage Tracking**: Memory and CPU usage monitoring for identifying bottlenecks
- **Optimized Algorithms**: Enhanced time range intersection algorithms for scheduling

### Real-time WebSocket Implementation

- **Efficient WebSocket Consumer**: Implemented optimized WebSocket consumer with security and performance features
- **Message Compression**: Automatic compression for large messages to reduce bandwidth
- **Rate Limiting**: Flood protection to prevent system overload
- **Connection Pooling**: Redis connection pooling for WebSockets to handle thousands of concurrent connections

### Advanced Admin Panel Features

- **Role Management System**: Comprehensive role-based access control with visual permission assignment
- **System Health Monitoring**: Real-time metrics dashboard for monitoring server performance, database connections, and API endpoints
- **Communications Hub**: Centralized interface for managing all customer and shop communications with filtering and search
- **Audit Logging System**: Detailed tracking of all administrative actions for security compliance and accountability

For detailed documentation on these features, see:
- [ADMIN_FEATURES_SUMMARY.md](ADMIN_FEATURES_SUMMARY.md)
- [AUDIT_LOGGING_DOCUMENTATION.md](AUDIT_LOGGING_DOCUMENTATION.md)
