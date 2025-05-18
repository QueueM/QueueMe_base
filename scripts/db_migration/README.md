# SQLite to PostgreSQL Migration Tool

This tool provides a robust, resumable migration process from SQLite to PostgreSQL for the QueueMe platform.

## Features

- Incremental migration with resumable processing
- Data validation to ensure integrity
- Proper handling of database sequences and relationships
- Batch processing for large datasets
- Detailed logging for troubleshooting

## Prerequisites

- PostgreSQL server installed and running
- Connection details for PostgreSQL database
- Python environment with required dependencies:
  - psycopg2-binary
  - Django environment configured

## Usage

```bash
# Basic usage
python sqlite_to_postgres.py --sqlite-path=db.sqlite3

# Resume previously interrupted migration
python sqlite_to_postgres.py --sqlite-path=db.sqlite3 --resume

# Clean target database before migration
python sqlite_to_postgres.py --sqlite-path=db.sqlite3 --clean

# Control batch size for large databases
python sqlite_to_postgres.py --sqlite-path=db.sqlite3 --batch-size=5000
```

## Environment Variables

Set these environment variables to configure the PostgreSQL connection:

- `POSTGRES_DB`: Database name (default: "queueme")
- `POSTGRES_USER`: Username (default: "queueme")
- `POSTGRES_PASSWORD`: Password
- `POSTGRES_HOST`: Database host (default: "localhost")
- `POSTGRES_PORT`: Database port (default: "5432")

## Migration Process

1. The script analyzes table dependencies to determine the migration order
2. Each table is exported in batches to CSV files
3. Data is imported to PostgreSQL using efficient batch operations
4. Validation is performed to ensure row counts match
5. Sequences are reset to match the highest ID in each table

## Resuming Interrupted Migrations

If the migration is interrupted, it will automatically save its progress in a state file (`.migration_state.json`).
Run the script with the `--resume` flag to continue from where it left off.

## Troubleshooting

- Check the log file (`db_migration.log`) for detailed error information
- For data inconsistencies, examine the validation output in the logs
- Make sure your PostgreSQL server has enough resources (memory, disk space)
