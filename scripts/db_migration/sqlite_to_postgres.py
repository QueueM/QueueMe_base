#!/usr/bin/env python
# =============================================================================
# Queue Me SQLite to PostgreSQL Migration
# Advanced database migration with validation, foreign key preservation,
# and resumable processing
# =============================================================================

import argparse
import csv
import json
import logging
import os
import sqlite3
import sys
import tempfile
import time
from datetime import datetime

import django
import psycopg2
from django.apps import apps

# Setup Django environment
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "queueme.settings.production")
django.setup()


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(BASE_DIR, "db_migration.log")),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


class DBMigrator:
    def __init__(self, sqlite_path, pg_config, batch_size=1000, resume_file=None):
        """Initialize the migrator with database connections and settings"""
        self.sqlite_path = sqlite_path
        self.pg_config = pg_config
        self.batch_size = batch_size
        self.resume_file = resume_file or os.path.join(
            os.path.dirname(__file__), ".migration_state.json"
        )
        self.state = self._load_state()

        # Connect to databases
        self.sqlite_conn = None
        self.pg_conn = None

        # Track progress
        self.total_tables = 0
        self.tables_processed = 0
        self.total_rows = 0
        self.rows_processed = 0

    def _load_state(self):
        """Load migration state from file if it exists"""
        if os.path.exists(self.resume_file):
            try:
                with open(self.resume_file, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.warning("Could not parse resume state file. Starting fresh.")

        return {
            "completed_tables": [],
            "current_table": None,
            "rows_completed": 0,
            "started_at": datetime.now().isoformat(),
        }

    def _save_state(self):
        """Save migration state to file"""
        with open(self.resume_file, "w") as f:
            json.dump(self.state, f)

    def connect(self):
        """Connect to both databases"""
        logger.info("Connecting to databases...")
        try:
            self.sqlite_conn = sqlite3.connect(self.sqlite_path)
            self.sqlite_conn.row_factory = sqlite3.Row

            self.pg_conn = psycopg2.connect(**self.pg_config)
            self.pg_conn.autocommit = False

            return True
        except Exception as e:
            logger.error(f"Connection error: {str(e)}")
            return False

    def close(self):
        """Close database connections"""
        if self.sqlite_conn:
            self.sqlite_conn.close()
        if self.pg_conn:
            self.pg_conn.close()

    def get_all_tables(self):
        """Get sorted tables from SQLite that need migration"""
        cursor = self.sqlite_conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [
            table[0]
            for table in cursor.fetchall()
            if table[0] != "sqlite_sequence"
            and not table[0].startswith("django_migrations")
            and not table[0] in self.state["completed_tables"]
        ]
        cursor.close()

        # Sort tables based on dependencies
        return self._sort_tables_by_dependencies(tables)

    def _sort_tables_by_dependencies(self, tables):
        """Sort tables topologically based on foreign key dependencies"""
        app_configs = apps.get_app_configs()
        models = []

        for app in app_configs:
            models.extend(app.get_models())

        # Create mapping from table name to model
        table_to_model = {}
        for model in models:
            table_to_model[model._meta.db_table] = model

        # Filter models to only those in our tables list
        relevant_models = [
            table_to_model[table] for table in tables if table in table_to_model
        ]

        # Sort models topologically
        sorted_models = []
        processed_models = set()

        def process_model(model):
            if model in processed_models:
                return

            # Process models this one depends on first
            for field in model._meta.fields:
                if field.is_relation and field.remote_field.model != model:
                    related_model = field.remote_field.model
                    if related_model in relevant_models:
                        process_model(related_model)

            processed_models.add(model)
            sorted_models.append(model)

        # Process all models
        for model in relevant_models:
            process_model(model)

        # Get sorted table names
        sorted_tables = [model._meta.db_table for model in sorted_models]

        # Add any remaining tables not in Django models
        for table in tables:
            if table not in sorted_tables:
                sorted_tables.append(table)

        return sorted_tables

    def get_table_info(self, table_name):
        """Get column info for a table"""
        cursor = self.sqlite_conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = [col[1] for col in cursor.fetchall()]
        cursor.close()
        return columns

    def count_rows(self, table_name):
        """Count total rows in a table"""
        cursor = self.sqlite_conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
        count = cursor.fetchone()[0]
        cursor.close()
        return count

    def export_table_to_csv(self, table_name, columns, start_row=0):
        """Export a table to CSV file"""
        temp_file = tempfile.NamedTemporaryFile(mode="w+", delete=False)
        cursor = self.sqlite_conn.cursor()

        # Write header
        writer = csv.writer(temp_file)
        writer.writerow(columns)

        # Get total rows for this batch
        rows_to_fetch = min(self.batch_size, self.count_rows(table_name) - start_row)
        logger.info(
            f"Exporting batch of {rows_to_fetch} rows from {table_name} starting at {start_row}"
        )

        # Write data in batches
        cursor.execute(
            f"SELECT * FROM {table_name} LIMIT {rows_to_fetch} OFFSET {start_row};"
        )

        for row in cursor:
            # Convert row to list with proper handling of None values
            row_list = []
            for col_name in columns:
                col_index = cursor.description.index(col_name)
                row_list.append(row[col_index] if col_index < len(row) else None)

            writer.writerow(row_list)

        temp_file.close()
        cursor.close()

        return temp_file.name, rows_to_fetch

    def import_csv_to_postgres(self, table_name, csv_file, columns):
        """Import data from CSV to PostgreSQL"""
        cursor = self.pg_conn.cursor()

        # Format column list for SQL query
        column_list = ", ".join([f'"{col}"' for col in columns])
        placeholders = ", ".join(["%s"] * len(columns))

        # Read CSV and insert rows
        with open(csv_file, "r") as f:
            csv_reader = csv.reader(f)
            next(csv_reader)  # Skip header

            rows = []
            for row in csv_reader:
                # Convert empty strings to None
                processed_row = [None if v == "" else v for v in row]
                rows.append(processed_row)

            # Use efficient batch insertion
            try:
                psycopg2.extras.execute_batch(
                    cursor,
                    f'INSERT INTO "{table_name}" ({column_list}) VALUES ({placeholders}) '
                    + "ON CONFLICT DO NOTHING;",
                    rows,
                    page_size=100,
                )
                self.pg_conn.commit()
            except Exception as e:
                self.pg_conn.rollback()
                logger.error(f"Error importing data to {table_name}: {e}")
                raise

        cursor.close()

        # Clean up temp file
        os.unlink(csv_file)

    def migrate_table(self, table_name):
        """Migrate a single table with resumable batching"""
        logger.info(f"Migrating table: {table_name}")

        # Update state
        self.state["current_table"] = table_name
        start_row = (
            self.state["rows_completed"]
            if self.state["current_table"] == table_name
            else 0
        )
        self.state["rows_completed"] = start_row
        self._save_state()

        try:
            # Get column info
            columns = self.get_table_info(table_name)
            total_rows = self.count_rows(table_name)

            # Process in batches
            while start_row < total_rows:
                csv_file, rows_processed = self.export_table_to_csv(
                    table_name, columns, start_row
                )
                self.import_csv_to_postgres(table_name, csv_file, columns)

                start_row += rows_processed
                self.state["rows_completed"] = start_row
                self._save_state()

                logger.info(f"Processed {start_row}/{total_rows} rows of {table_name}")

            # Table completed
            self.state["completed_tables"].append(table_name)
            self.state["current_table"] = None
            self.state["rows_completed"] = 0
            self._save_state()

            logger.info(f"✓ Successfully migrated {table_name}")
            return True

        except Exception as e:
            logger.error(f"✗ Error migrating {table_name}: {str(e)}")
            return False

    def validate_migration(self, table_name):
        """Validate migration by comparing row counts"""
        sqlite_cursor = self.sqlite_conn.cursor()
        sqlite_cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
        sqlite_count = sqlite_cursor.fetchone()[0]
        sqlite_cursor.close()

        pg_cursor = self.pg_conn.cursor()
        pg_cursor.execute(f'SELECT COUNT(*) FROM "{table_name}";')
        pg_count = pg_cursor.fetchone()[0]
        pg_cursor.close()

        if sqlite_count == pg_count:
            logger.info(f"✓ Validation successful for {table_name}: {pg_count} rows")
            return True
        else:
            logger.warning(
                f"⚠ Validation failed for {table_name}: SQLite has {sqlite_count} rows, PostgreSQL has {pg_count} rows"
            )
            return False

    def reset_sequences(self):
        """Reset sequences in PostgreSQL tables"""
        logger.info("Resetting PostgreSQL sequences...")
        cursor = self.pg_conn.cursor()

        # Get all sequences
        cursor.execute(
            """
            SELECT sequence_name
            FROM information_schema.sequences
            WHERE sequence_schema='public'
        """
        )

        sequences = cursor.fetchall()
        for seq in sequences:
            seq_name = seq[0]
            table_name = seq_name.replace("_id_seq", "")

            try:
                # Get max ID from table
                cursor.execute(f'SELECT MAX(id) FROM "{table_name}";')
                max_id = cursor.fetchone()[0]

                if max_id is not None:
                    # Set sequence to max ID + 1
                    cursor.execute(f"SELECT setval('{seq_name}', {max_id});")
                    logger.info(f"✓ Reset sequence {seq_name} to {max_id}")
            except Exception as e:
                logger.warning(f"⚠ Could not reset sequence {seq_name}: {str(e)}")

        self.pg_conn.commit()
        cursor.close()

    def migrate(self):
        """Run the full migration process"""
        start_time = time.time()
        logger.info("Starting SQLite to PostgreSQL migration...")

        if not self.connect():
            return False

        try:
            # Get tables to migrate
            tables = self.get_all_tables()
            self.total_tables = len(tables)
            logger.info(f"Found {self.total_tables} tables to migrate.")

            # Migrate each table
            for table in tables:
                if self.migrate_table(table):
                    self.tables_processed += 1
                    # Validate after each table
                    self.validate_migration(table)

            # Reset sequences
            self.reset_sequences()

            # Final summary
            elapsed_time = time.time() - start_time
            logger.info(
                f"Migration completed! Processed {self.tables_processed}/{self.total_tables} tables in {elapsed_time:.2f} seconds"
            )

            # Clear resume state file if completed successfully
            if len(self.state["completed_tables"]) == self.total_tables:
                if os.path.exists(self.resume_file):
                    os.remove(self.resume_file)
                logger.info("Migration state cleared - process completed successfully")

            return self.tables_processed == self.total_tables

        finally:
            self.close()


def main():
    parser = argparse.ArgumentParser(
        description="Migrate data from SQLite to PostgreSQL."
    )
    parser.add_argument(
        "--sqlite-path", default="db.sqlite3", help="Path to SQLite database file"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Number of rows to process in each batch",
    )
    parser.add_argument(
        "--resume", action="store_true", help="Resume from last position"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean existing data in PostgreSQL before migration",
    )
    args = parser.parse_args()

    # Get PostgreSQL config from environment or settings
    pg_config = {
        "dbname": os.environ.get("POSTGRES_DB", "queueme"),
        "user": os.environ.get("POSTGRES_USER", "queueme"),
        "password": os.environ.get("POSTGRES_PASSWORD", "queueme"),
        "host": os.environ.get("POSTGRES_HOST", "localhost"),
        "port": os.environ.get("POSTGRES_PORT", "5432"),
    }

    # Clean PostgreSQL if requested
    if args.clean:
        clean_postgres(pg_config)

    # Create migrator and run migration
    migrator = DBMigrator(
        sqlite_path=args.sqlite_path,
        pg_config=pg_config,
        batch_size=args.batch_size,
        resume_file=(
            None if not args.resume else None
        ),  # Use default resume file if resuming
    )

    success = migrator.migrate()

    if success:
        logger.info("Migration completed successfully!")
        return 0
    else:
        logger.error("Migration failed.")
        return 1


def clean_postgres(pg_config):
    """Clean existing data in PostgreSQL database"""
    logger.info("Cleaning PostgreSQL database...")

    try:
        conn = psycopg2.connect(**pg_config)
        conn.autocommit = True
        cursor = conn.cursor()

        # Disable triggers
        cursor.execute("SET session_replication_role = 'replica';")

        # Get all tables
        cursor.execute(
            """
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public' AND tablename != 'django_migrations';
        """
        )

        tables = [table[0] for table in cursor.fetchall()]

        # Truncate all tables (except migrations)
        for table in tables:
            logger.info(f"Truncating table {table}")
            cursor.execute(f'TRUNCATE TABLE "{table}" CASCADE;')

        # Re-enable triggers
        cursor.execute("SET session_replication_role = 'origin';")

        logger.info("Database cleaned successfully")

    except Exception as e:
        logger.error(f"Error cleaning database: {str(e)}")
        return False
    finally:
        if "conn" in locals():
            conn.close()

    return True


if __name__ == "__main__":
    sys.exit(main())
