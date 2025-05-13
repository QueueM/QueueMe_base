# Performance Optimization Guide for QueueMe

This guide provides detailed instructions for configuring and enabling the performance optimizations implemented in the QueueMe platform.

## Table of Contents
1. [Database Query Optimization](#1-database-query-optimization)
2. [Geospatial Indexing](#2-geospatial-indexing)
3. [CDN Integration for Media Content](#3-cdn-integration-for-media-content)
4. [Additional Performance Tuning](#4-additional-performance-tuning)

## 1. Database Query Optimization

The QueueMe platform now includes advanced query optimization tools to identify and fix slow database queries.

### Configuration

Add the following settings to your `settings.py` file:

```python
# Query optimization settings
QUERY_SAMPLING_RATE = 0.1  # Sample 10% of queries for analysis
SLOW_QUERY_THRESHOLD_MS = 200  # Log queries taking longer than 200ms
MAX_QUERIES_PER_REQUEST = 50  # Log excessive queries per request
QUERY_LOG_SIZE = 1000  # Keep the most recent 1000 slow queries
ENABLE_QUERY_OPTIMIZATION = True  # Enable automatic query optimization
```

### Usage

#### Tracking Queries in Views

```python
from core.utils.query_optimizer import track_queries

@track_queries()
def my_view(request):
    # Your view code here
    return response
```

#### Analyzing and Optimizing Querysets

```python
from core.utils.query_optimizer import analyze_queryset, optimize_queryset

# Check a queryset for optimization opportunities
queryset = MyModel.objects.filter(status='active')
analysis = analyze_queryset(queryset)
print(analysis['suggestions'])

# Automatically optimize a queryset
optimized_qs = optimize_queryset(queryset)
```

#### Getting Performance Reports

```python
from core.utils.query_optimizer import get_slow_query_report, get_query_stats

# Get a report of slow queries
report = get_slow_query_report()

# Get statistics by view/path
stats = get_query_stats()
```

#### Index Suggestions

```python
from core.utils.query_optimizer import suggest_indexes

# Get index suggestions for a model
suggestions = suggest_indexes(MyModel)
```

### Common Optimizations

1. **Use `select_related` for foreign keys**:
   ```python
   # Bad
   order = Order.objects.get(id=1)
   customer = order.customer  # Extra query

   # Good
   order = Order.objects.select_related('customer').get(id=1)
   customer = order.customer  # No extra query
   ```

2. **Use `prefetch_related` for reverse relationships**:
   ```python
   # Bad
   customers = Customer.objects.all()
   for customer in customers:
       orders = customer.orders.all()  # Extra query per customer

   # Good
   customers = Customer.objects.prefetch_related('orders')
   for customer in customers:
       orders = customer.orders.all()  # No extra queries
   ```

3. **Use `values()` or `values_list()` for simple data**:
   ```python
   # When you only need specific fields
   names = Customer.objects.values_list('name', flat=True)
   ```

4. **Add indexes to commonly filtered fields**:
   ```python
   class Meta:
       indexes = [
           models.Index(fields=['status']),
           models.Index(fields=['created_at']),
       ]
   ```

## 2. Geospatial Indexing

QueueMe now uses GeoDjango and PostGIS for efficient location-based queries.

### Prerequisites

1. **PostGIS Installation**:
   ```bash
   # Ubuntu/Debian
   sudo apt-get install postgis postgresql-12-postgis-3

   # macOS (with Homebrew)
   brew install postgis
   ```

2. **Enable PostGIS in your database**:
   ```sql
   CREATE EXTENSION postgis;
   ```

### Configuration

Update your `settings.py`:

```python
INSTALLED_APPS = [
    # ...
    'django.contrib.gis',
    # ...
]

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        # Other database settings
    }
}

# Geospatial settings
MAX_GEO_DISTANCE_KM = 100  # Maximum radius for geo queries
GEO_DISTANCE_PRECISION = 2  # Decimal places for distances
```

### Usage

```python
from apps.geoapp.utils.spatial_optimizations import (
    optimize_point_distance_query,
    get_points_in_polygon,
    create_bounding_box,
    optimize_geofence_query
)
from django.contrib.gis.geos import Point

# Find shops near a location with optimized query
user_location = Point(longitude, latitude, srid=4326)
nearby_shops = optimize_point_distance_query(
    Shop.objects.all(),
    user_location,
    distance_km=10
)

# Find points within a polygon (e.g., delivery area)
shops_in_area = get_points_in_polygon(
    Shop.objects.all(),
    polygon_object,
    distance_ordered=True,
    reference_point=user_location
)

# Check if user is in active geofences
active_geofences = optimize_geofence_query(
    Geofence.objects.all(),
    user_location
)
```

### Applying Migrations

Run the migration to set up spatial fields and indexes:

```bash
python manage.py migrate geoapp
```

## 3. CDN Integration for Media Content

QueueMe now supports multiple CDN providers for efficient media delivery.

### Configuration

Add the following to your `settings.py`:

```python
# Basic CDN settings
CDN_URL = 'https://cdn.yourdomain.com/'  # Your CDN base URL
CDN_PROVIDER = 'cloudfront'  # 'cloudfront', 'akamai', 's3', or 'custom'
CDN_CACHE_CONTROL = 'public, max-age=86400'  # Default cache control header
CDN_ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.mp4', '.webm', '.mp3', '.pdf', '.svg']
CDN_MAX_AGE_SECONDS = 86400  # 24 hours default TTL

# AWS/CloudFront settings (if using AWS)
AWS_STORAGE_BUCKET_NAME = 'your-bucket-name'
AWS_S3_REGION_NAME = 'us-east-1'
AWS_S3_CUSTOM_DOMAIN = 'cdn.yourdomain.com'
CLOUDFRONT_KEY_ID = 'your-cloudfront-key-id'  # For private content
CLOUDFRONT_PRIVATE_KEY = 'your-cloudfront-private-key'  # For private content
CLOUDFRONT_DISTRIBUTION_ID = 'your-distribution-id'

# Storage settings
DEFAULT_FILE_STORAGE = 'core.storage.cdn_storage.MediaCDNStorage'
STATICFILES_STORAGE = 'core.storage.cdn_storage.StaticCDNStorage'
```

### Using Dynamic Image Resizing

```python
from core.storage.cdn_storage import dynamic_image_storage

# Get a URL for a resized image
resized_url = dynamic_image_storage.resize(width=300, height=200).url('path/to/image.jpg')
```

### Purging Cache

```python
from core.storage.cdn_storage import media_cdn_storage

# Purge a single file
media_cdn_storage.purge_file('path/to/file.jpg')

# Clear cache for multiple patterns
media_cdn_storage.clear_cache(['images/*', 'videos/*'])
```

## 4. Additional Performance Tuning

### Database Connection Pooling

Add the following to your `settings.py`:

```python
DATABASES = {
    'default': {
        # ...existing settings...
        'CONN_MAX_AGE': 60,  # Keep connections alive for 60 seconds
        'OPTIONS': {
            'MAX_CONNS': 100,  # Maximum number of connections in the pool
        }
    }
}
```

### Redis Caching

```python
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'PARSER_CLASS': 'redis.connection.HiredisParser',
            'CONNECTION_POOL_KWARGS': {'max_connections': 100},
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
        }
    },
    'local': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}
```

### NGINX Configuration

Optimize your NGINX configuration for performance:

```nginx
# Enable gzip compression
gzip on;
gzip_comp_level 5;
gzip_min_length 256;
gzip_proxied any;
gzip_vary on;
gzip_types
  application/javascript
  application/json
  application/x-javascript
  application/xml
  application/xml+rss
  text/css
  text/javascript
  text/plain
  text/xml;

# Cache static files
location /static/ {
    expires 1y;
    add_header Cache-Control "public, max-age=31536000, immutable";
    access_log off;
}

# Cache media files
location /media/ {
    expires 7d;
    add_header Cache-Control "public, max-age=604800";
    access_log off;
}

# Add browser hints
add_header X-Content-Type-Options nosniff;
add_header X-Frame-Options SAMEORIGIN;
add_header X-XSS-Protection "1; mode=block";
```

### WebP Conversion

Add automatic WebP conversion for images:

```python
# Add to settings.py
INSTALLED_APPS += ['webp_converter']

WEBP_CONVERTER_ENABLED = True
WEBP_CONVERTER_QUALITY = 80
WEBP_CONVERTER_PREFIX = 'webp_'
```

## Monitoring Performance

1. **Set up Django Debug Toolbar** (development only):
   ```python
   INSTALLED_APPS += ['debug_toolbar']
   MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
   INTERNAL_IPS = ['127.0.0.1']
   ```

2. **Enable query logging** (development only):
   ```python
   LOGGING = {
       # ... existing config ...
       'loggers': {
           'django.db.backends': {
               'level': 'DEBUG',
               'handlers': ['console'],
           },
       },
   }
   ```

3. **Set up Prometheus monitoring** (production):
   ```python
   INSTALLED_APPS += ['django_prometheus']
   MIDDLEWARE = ['django_prometheus.middleware.PrometheusBeforeMiddleware'] + MIDDLEWARE
   MIDDLEWARE += ['django_prometheus.middleware.PrometheusAfterMiddleware']
   ```
