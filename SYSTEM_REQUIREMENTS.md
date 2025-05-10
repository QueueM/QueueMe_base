# System Requirements for QueueMe on Ubuntu 24.04

This document outlines the minimum and recommended system requirements for running QueueMe on Ubuntu 24.04 LTS (Noble Numbat).

## Hardware Requirements

### Minimum Requirements

- **CPU**: 2 cores
- **RAM**: 2GB
- **Storage**: 20GB SSD
- **Network**: 100 Mbps

### Recommended Requirements

- **CPU**: 4+ cores
- **RAM**: 8GB+
- **Storage**: 50GB+ SSD
- **Network**: 1 Gbps

### Production Environment Recommendations

For production environments with significant traffic (100+ concurrent users):

- **CPU**: 8+ cores
- **RAM**: 16GB+
- **Storage**: 100GB+ SSD with backup solution
- **Network**: 1 Gbps with redundancy

## Operating System

- **Required**: Ubuntu 24.04 LTS (Noble Numbat)
- **Architecture**: 64-bit (x86_64/amd64)
- **Kernel**: 6.8.0 or later (included with Ubuntu 24.04)

## Software Dependencies

### Core Dependencies

- **Python**: 3.11+
- **PostgreSQL**: 16+
- **Redis**: 7.2+
- **Nginx**: 1.24+
- **Supervisor**: 4.2+

### Python Package Dependencies

All Python dependencies are listed in `requirements.txt`, with key packages including:

- **Django**: 4.2.7
- **Django REST Framework**: 3.14.0
- **Channels**: 4.0.0
- **Celery**: 5.3.4
- **psycopg2-binary**: 2.9.10
- **Gunicorn**: 21.2.0
- **Daphne**: 4.0.0

### PostGIS Requirements

The GIS functionality requires PostGIS, which includes these components:

- PostgreSQL with PostGIS extension
- GDAL libraries
- GEOS libraries
- PROJ.4 libraries

## Storage Requirements

QueueMe requires separate storage allocations for:

1. **Database**: 
   - Starting size: 500MB
   - Growth estimate: ~100MB per 1,000 bookings

2. **Media files** (user uploads):
   - Starting size: 100MB
   - Growth estimate: ~1GB per 1,000 users (assuming profile photos and service images)

3. **Static files** (CSS, JS, images):
   - Fixed size: ~50MB

4. **Log files**:
   - Growth estimate: ~100MB per month
   - Recommend log rotation policies

## Network Requirements

- **Inbound ports**: 80 (HTTP), 443 (HTTPS), 22 (SSH)
- **Outbound access** required for:
  - Email services (SMTP)
  - SMS services (Twilio API)
  - Payment gateways (Moyasar)
  - S3 storage (if used)

## Memory Allocation Guidelines

For optimal performance, allocate memory as follows:

- **PostgreSQL**: 25% of system RAM
  - Example: 2GB RAM on an 8GB system
- **Redis**: 256MB minimum
- **Gunicorn workers**: (2 × num_cores) + 1
  - Example: 9 workers on a 4-core system
- **Celery workers**: num_cores

## User Requirements

- A non-root user with sudo privileges for managing the application
- Dedicated service users (www-data) for running the web services
- Database user with appropriate permissions

## Backup Requirements

- Minimum 2x the total storage space for rotating backups
- Off-site backup capability
- Database backup solution (pg_dump)
- Media files backup solution

## Optional Components

- **SSL Certificate**: Let's Encrypt recommended
- **CDN**: For global deployments
- **Load Balancer**: For high-traffic deployments
- **Memory Caching**: Additional Redis instance for cache-only operations
- **Monitoring Tools**: Prometheus, Grafana, etc.

## Development Environment

For development environments, the requirements can be relaxed:

- **CPU**: 2 cores
- **RAM**: 4GB
- **Storage**: 20GB
- **OS**: Ubuntu 24.04 Desktop or WSL2 on Windows 