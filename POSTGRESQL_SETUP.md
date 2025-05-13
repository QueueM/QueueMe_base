# PostgreSQL Setup for QueueMe

This guide provides instructions for setting up PostgreSQL for the QueueMe platform, including migration from SQLite and performance optimization.

## Installation

### Ubuntu/Debian
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib postgresql-client libpq-dev
```

### MacOS
```bash
brew install postgresql
brew services start postgresql
```

## Database Setup

1. Create a database and user:
```bash
sudo -u postgres psql

postgres=# CREATE DATABASE queueme;
postgres=# CREATE USER queueme WITH PASSWORD 'your_secure_password';
postgres=# ALTER ROLE queueme SET client_encoding TO 'utf8';
postgres=# ALTER ROLE queueme SET default_transaction_isolation TO 'read committed';
postgres=# ALTER ROLE queueme SET timezone TO 'UTC';
postgres=# GRANT ALL PRIVILEGES ON DATABASE queueme TO queueme;
postgres=# \q
```

2. Update your .env file with PostgreSQL details:
```
DB_ENGINE=django.db.backends.postgresql
DB_NAME=queueme
DB_USER=queueme
DB_PASSWORD=your_secure_password
DB_HOST=localhost
DB_PORT=5432
```

## Migration from SQLite to PostgreSQL

We provide a migration script that handles transferring data from SQLite to PostgreSQL:

```bash
# Make sure PostgreSQL dependencies are installed
pip install -r requirements/base.txt

# Run the migration script
python scripts/db_migration/sqlite_to_postgres.py --sqlite-path=db.sqlite3
```

For advanced options and detailed information, check the [Migration README](scripts/db_migration/README.md).

## Performance Optimizations

### Database Indexes

The platform has optimized database indexes for better query performance:

- Queue tables with indexes on status, customer, specialist, position and check-in time
- Geospatial indexes for location-based queries
- Composite indexes for common queries

### Connection Pooling

For production environments, configure connection pooling:

1. Install pgbouncer:
```bash
sudo apt install pgbouncer
```

2. Configure pgbouncer in `/etc/pgbouncer/pgbouncer.ini`:
```ini
[databases]
queueme = host=127.0.0.1 port=5432 dbname=queueme

[pgbouncer]
listen_addr = 127.0.0.1
listen_port = 6432
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = transaction
default_pool_size = 20
max_client_conn = 100
```

3. Update your .env to use pgbouncer:
```
DB_HOST=127.0.0.1
DB_PORT=6432
```

### Query Monitoring

The platform includes a database query monitoring system that:

1. Tracks slow queries and reports them in logs
2. Provides query statistics through the admin interface
3. Helps identify optimization opportunities

To enable it, add to your .env:
```
PERFORMANCE_MONITORING=True
SLOW_QUERY_THRESHOLD=0.5
```

## Backup and Restore

Set up regular backups:

```bash
# Create a backup script
cat > backup_db.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/path/to/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
pg_dump -U queueme -d queueme -F c -f "$BACKUP_DIR/queueme_$TIMESTAMP.backup"
EOF

chmod +x backup_db.sh

# Set up cron to run daily
crontab -e
# Add: 0 2 * * * /path/to/backup_db.sh
```

To restore:
```bash
pg_restore -U queueme -d queueme -c /path/to/backup_file
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
