# Redis Setup for QueueMe on Ubuntu 24.04

This guide provides instructions for setting up and optimizing Redis for QueueMe on Ubuntu 24.04 LTS.

## Installation

First, install Redis:

```bash
# Update package lists
sudo apt update

# Install Redis
sudo apt install -y redis-server
```

## Configuration

### 1. Basic Configuration

Edit the Redis configuration file:

```bash
sudo nano /etc/redis/redis.conf
```

Make the following recommended changes:

```
# Bind Redis to listen on all interfaces (if needed)
# WARNING: Only do this if Redis is properly secured!
bind 127.0.0.1 ::1

# Set a password (recommended for production)
requirepass your_strong_password_here

# Memory management
maxmemory 256mb
maxmemory-policy allkeys-lru

# Enable AOF persistence for better data durability
appendonly yes
appendfilename "appendonly.aof"
appendfsync everysec

# Snapshotting configuration
save 900 1
save 300 10
save 60 10000

# Performance tuning
tcp-keepalive 300
timeout 0
tcp-backlog 511

# Logging
loglevel notice
```

### 2. System Configuration

Configure the system for Redis:

```bash
# Allow Redis to use memory overcommit
sudo sysctl vm.overcommit_memory=1

# To make this change persistent
echo "vm.overcommit_memory = 1" | sudo tee -a /etc/sysctl.conf

# Disable transparent huge pages (recommended for Redis)
echo never | sudo tee /sys/kernel/mm/transparent_hugepage/enabled
```

### 3. Configure Redis for Systemd

Ensure Redis is enabled and configured to start on boot:

```bash
sudo systemctl enable redis-server
sudo systemctl restart redis-server
```

## Testing Redis

Verify that Redis is running correctly:

```bash
# Check Redis status
sudo systemctl status redis-server

# Connect to Redis
redis-cli

# If you set a password
redis-cli -a your_strong_password_here

# Test basic functionality
127.0.0.1:6379> PING
PONG

# Set and get a key
127.0.0.1:6379> SET test "Hello QueueMe"
OK
127.0.0.1:6379> GET test
"Hello QueueMe"

# Exit Redis CLI
127.0.0.1:6379> EXIT
```

## Redis for QueueMe

QueueMe uses Redis for several key functions:

1. **Caching**: Optimizing database queries
2. **Session Storage**: Managing user sessions
3. **Celery Task Queue**: Background tasks and scheduling
4. **WebSocket Channels**: Real-time communication
5. **Rate Limiting**: Protecting API endpoints

### Project-Specific Configuration

For QueueMe, consider the following Redis database allocations:

- DB 0: Celery task queue and results
- DB 1: Django cache
- DB 2: Channels (WebSockets)
- DB 3: Session store
- DB 4: Rate limiting

Update your `.env` file to include these Redis settings:

```
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_URL=redis://localhost:6379/1
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

Update your Django settings to use Redis for cache and sessions:

```python
# Cache settings
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://localhost:6379/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "CONNECTION_POOL_KWARGS": {"max_connections": 100},
            "PARSER_CLASS": "redis.connection.HiredisParser",
            "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
        },
        "KEY_PREFIX": "queueme",
    }
}

# Session configuration
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

# Channels configuration
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [("localhost", 6379)],
            "capacity": 1500,
            "expiry": 10,
        },
    },
}
```

## Monitoring Redis

### Redis CLI Commands for Monitoring

```bash
# Connect to Redis
redis-cli

# Get server information
INFO

# Get memory usage statistics
INFO memory

# Monitor commands in real-time
MONITOR

# Get list of clients
CLIENT LIST

# Get slow log
SLOWLOG GET 10

# Get database statistics
INFO keyspace
```

### Using Redis Commander (Optional)

Redis Commander is a web-based Redis management tool:

```bash
# Install Redis Commander
sudo apt install -y npm
sudo npm install -g redis-commander

# Run Redis Commander (secured with basic auth)
redis-commander --redis-host 127.0.0.1 --redis-port 6379 --http-auth-username admin --http-auth-password password

# Access Redis Commander at: http://your_server_ip:8081
```

## Backup and Restore

### Creating Redis Backups

```bash
# Manual backup using SAVE command
redis-cli SAVE

# Backup using redis-cli and copy the dump.rdb file
sudo cp /var/lib/redis/dump.rdb /backup/redis_backup_$(date +%Y-%m-%d).rdb

# For AOF-enabled Redis
sudo cp /var/lib/redis/appendonly.aof /backup/redis_aof_backup_$(date +%Y-%m-%d).aof
```

### Restoring from Backup

```bash
# Stop Redis
sudo systemctl stop redis-server

# Replace dump.rdb with the backup
sudo cp /backup/redis_backup_YYYY-MM-DD.rdb /var/lib/redis/dump.rdb

# Fix ownership
sudo chown redis:redis /var/lib/redis/dump.rdb

# Start Redis
sudo systemctl start redis-server
```

## Troubleshooting

### Common Issues and Solutions

1. **Redis won't start**:
   - Check logs: `sudo tail -f /var/log/redis/redis-server.log`
   - Verify Redis configuration: `redis-cli -h localhost -p 6379 CONFIG GET '*'`
   - Check disk space: `df -h`

2. **Connection refused errors**:
   - Check Redis is running: `sudo systemctl status redis-server`
   - Verify bind settings in redis.conf
   - Check firewall rules if connecting remotely

3. **Memory issues**:
   - Adjust maxmemory setting in redis.conf
   - Monitor memory usage: `redis-cli INFO memory`
   - Consider Redis eviction policies

4. **Poor performance**:
   - Check for slow commands: `redis-cli SLOWLOG GET 10`
   - Ensure transparent huge pages are disabled
   - Monitor CPU usage and disk I/O
   - Consider activating the io-threads feature for high throughput (Redis 6+)

5. **Persistence problems**:
   - Verify AOF status: `redis-cli CONFIG GET appendonly`
   - Check AOF rewrite status: `redis-cli INFO persistence`
