# PostgreSQL Setup for QueueMe on Ubuntu 24.04

This guide provides instructions for setting up PostgreSQL with PostGIS for QueueMe on Ubuntu 24.04 LTS.

## Installation

First, install PostgreSQL and PostGIS:

```bash
# Update package lists
sudo apt update

# Install PostgreSQL
sudo apt install -y postgresql postgresql-contrib postgresql-client

# Get PostgreSQL version
PG_VERSION=$(psql --version | awk '{print $3}' | cut -d'.' -f1)

# Install PostGIS
sudo apt install -y postgis postgresql-${PG_VERSION}-postgis-3
```

## Configuration

### 1. Create Database User and Database

```bash
# Create database user
sudo -u postgres psql -c "CREATE USER queueme WITH PASSWORD 'queueme' CREATEDB;"

# Create database
sudo -u postgres psql -c "CREATE DATABASE queueme WITH OWNER queueme;"

# Enable PostGIS extension
sudo -u postgres psql -d queueme -c "CREATE EXTENSION IF NOT EXISTS postgis;"
```

### 2. PostgreSQL Configuration Optimization

Edit the PostgreSQL configuration file to optimize it for QueueMe:

```bash
sudo nano /etc/postgresql/${PG_VERSION}/main/postgresql.conf
```

Make the following changes based on your server's resources:

```
# Memory settings
shared_buffers = 256MB                  # Adjust based on available RAM (25% of RAM)
work_mem = 16MB                         # Adjust based on query complexity
maintenance_work_mem = 64MB             # Adjust based on available RAM

# Query Optimization
effective_cache_size = 768MB            # Adjust based on available RAM (75% of RAM)
random_page_cost = 1.1                  # Assuming SSD storage

# Write Ahead Log
wal_buffers = 16MB                      # Typically 1/32 of shared_buffers

# Background Writer
bgwriter_delay = 200ms                  # Background writer sleep time
bgwriter_lru_maxpages = 100             # Max pages per round

# Connection Settings
max_connections = 100                   # Adjust based on expected load

# Checkpointing
checkpoint_timeout = 5min               # Time between checkpoints
checkpoint_completion_target = 0.9      # Checkpoint spread time

# Autovacuum Settings
autovacuum = on                         # Enable autovacuum
autovacuum_vacuum_scale_factor = 0.1    # Vacuum threshold
autovacuum_analyze_scale_factor = 0.05  # Analyze threshold

# Logging
log_min_duration_statement = 1000       # Log statements taking longer than 1s
log_checkpoints = on                    # Log checkpoints
log_connections = on                    # Log connections
log_disconnections = on                 # Log disconnections
log_lock_waits = on                     # Log lock waits
```

### 3. Client Authentication Configuration

Edit the client authentication configuration file:

```bash
sudo nano /etc/postgresql/${PG_VERSION}/main/pg_hba.conf
```

Add or modify the following lines:

```
# TYPE  DATABASE        USER            ADDRESS                 METHOD
local   all             postgres                                peer
local   all             queueme                                 md5
host    all             queueme         127.0.0.1/32            md5
host    all             queueme         ::1/128                 md5
```

### 4. Restart PostgreSQL

After making these changes, restart PostgreSQL:

```bash
sudo systemctl restart postgresql
```

## Testing the Connection

Test the connection to make sure everything is set up correctly:

```bash
# Connect to the database
psql -U queueme -d queueme -h localhost

# If successful, you should see a prompt like this:
# queueme=> 

# Test PostGIS
queueme=> SELECT PostGIS_version();

# Exit PostgreSQL
queueme=> \q
```

## Backup and Restore

### Creating Backups

```bash
# Backup the database
pg_dump -U queueme queueme > queueme_backup_$(date +%Y-%m-%d).sql

# Compressed backup
pg_dump -U queueme queueme | gzip > queueme_backup_$(date +%Y-%m-%d).sql.gz
```

### Restoring from Backup

```bash
# Restore from a backup file
psql -U queueme queueme < queueme_backup.sql

# Restore from a compressed backup
gunzip -c queueme_backup.sql.gz | psql -U queueme queueme
```

## Performance Monitoring

### Common PostgreSQL Monitoring Queries

Monitor active queries:

```sql
SELECT pid, age(clock_timestamp(), query_start), usename, query
FROM pg_stat_activity
WHERE query != '<IDLE>' AND query NOT ILIKE '%pg_stat_activity%'
ORDER BY query_start desc;
```

Find slow queries:

```sql
SELECT 
    substring(query, 1, 50) AS short_query,
    round(total_exec_time::numeric, 2) AS total_exec_time,
    calls,
    round(mean_exec_time::numeric, 2) AS mean,
    round((100 * total_exec_time / sum(total_exec_time::numeric) OVER ())::numeric, 2) AS percentage_cpu
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 20;
```

Table sizes:

```sql
SELECT
    relname AS "table_name",
    pg_size_pretty(pg_table_size(C.oid)) AS "table_size",
    pg_size_pretty(pg_indexes_size(C.oid)) AS "index_size",
    pg_size_pretty(pg_total_relation_size(C.oid)) AS "total_size"
FROM pg_class C
LEFT JOIN pg_namespace N ON (N.oid = C.relnamespace)
WHERE nspname NOT IN ('pg_catalog', 'information_schema')
AND C.relkind <> 'i'
AND nspname !~ '^pg_toast'
ORDER BY pg_total_relation_size(C.oid) DESC
LIMIT 20;
```

## Troubleshooting

### Common Issues and Solutions

1. **Connection refused error**: 
   - Check that PostgreSQL is running: `sudo systemctl status postgresql`
   - Verify pg_hba.conf settings allow your connection
   - Ensure the correct host/port/credentials are being used

2. **Permission denied errors**:
   - Check that the user has appropriate permissions
   - Verify file system permissions on data directory

3. **PostGIS extension not found**:
   - Ensure PostGIS is installed correctly: `sudo apt install -y postgis postgresql-${PG_VERSION}-postgis-3`
   - Try reinstalling if necessary

4. **High CPU usage**:
   - Check for long-running queries with: `SELECT * FROM pg_stat_activity WHERE state = 'active';`
   - Consider optimizing indexes or queries

5. **Database crashes**:
   - Check PostgreSQL logs: `sudo tail -f /var/log/postgresql/postgresql-${PG_VERSION}-main.log`
   - Check for out-of-memory issues in system logs 