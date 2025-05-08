# Queue Me - Advanced Queue and Appointment Management Platform

Queue Me is a sophisticated platform that connects customers from iOS app with service providers (shops) to manage bookings, services, reels, stories, live chat and specialists efficiently. It focuses on enhancing the customer experience through seamless scheduling, real-time updates, and flexible service options.

## Features

- **Dynamic Scheduling System** - Advanced scheduling with real-time availability calculation
- **Queue Management** - Sophisticated queue system for walk-in customers
- **Hybrid Appointments & Queues** - Intelligent integration of scheduled appointments and walk-ins
- **Specialist Management** - Comprehensive specialist profiles, scheduling, and workload balancing
- **Content Management** - Reels and Stories with 24-hour expiry for marketing content
- **Live Chat** - Real-time communication between customers and shops
- **Payment Processing** - Integrated with Moyassar for Saudi payment methods
- **Review System** - Multi-entity reviews (shops, specialists, services)
- **Geolocation Services** - Location-based visibility and distance calculations
- **Multi-language Support** - Complete Arabic and English localization

## Technical Overview

- **Backend**: Django REST Framework with advanced algorithmic components
- **Database**: SQLite3 (development), PostgreSQL (production-ready)
- **Caching**: Redis for session management and caching
- **Asynchronous Tasks**: Celery for background processing
- **Real-time Communication**: Django Channels for WebSockets
- **Storage**: AWS S3 for media files
- **Authentication**: Phone-based OTP verification

## Project Setup

### Prerequisites

- Python 3.9+
- Redis server
- PostgreSQL (for production)

### Development Setup

1. Clone the repository:
```bash
git clone https://github.com/QueueM/queueme_backend.git
cd queueme_backend