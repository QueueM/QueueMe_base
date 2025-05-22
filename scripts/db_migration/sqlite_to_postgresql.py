#!/usr/bin/env python3
"""
SQLite to PostgreSQL Migration Script

This script handles the migration of the Queue Me database from SQLite to PostgreSQL
with minimal downtime and maximum data integrity protection.

Usage:
    python sqlite_to_postgresql.py [--dry-run] [--config CONFIG_FILE]

Arguments:
    --dry-run         Test the migration without making changes
    --config          Path to configuration file (default: migration_config.json)
"""

import argparse
import json
import logging
import os
import sqlite3
import sys
import time
from datetime import datetime

import django
import psycopg2
from django.apps import apps
from django.conf import settings
from django.core.management import call_command

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("migration.log"), logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class DatabaseMigration:
    """
    Handles migration from SQLite to PostgreSQL
    """

    def __init__(self, config_file=None, dry_run=False):
        """
        Initialize migration with configuration

        Args:
            config_file: Path to configuration file
            dry_run: Whether to perform a test run without making changes
        """
        self.dry_run = dry_run
        self.config = self._load_config(config_file)
        self.started_at = datetime.now()
        self.tables_migrated = 0
        self.rows_migrated = 0
        self.errors = 0

        # Initialize Django if needed
        if not settings.configured:
            os.environ.setdefault("DJANGO_SETTINGS_MODULE", "queueme.settings")
            django.setup()

    def _load_config(self, config_file):
        """
        Load migration configuration from file

        Args:
            config_file: Path to configuration file

        Returns:
            Dictionary with configuration settings
        """
        default_config = {
            "sqlite_db": "db.sqlite3",
            "pg_dbname": "queueme",
            "pg_user": "postgres",
            "pg_password": "",
            "pg_host": "localhost",
            "pg_port": 5432,
            "batch_size": 5000,
            "timeout": 1800,  # 30 minutes
            "backup_dir": "backups",
            "exclude_tables": ["django_migrations"],
            "maintenance_mode": True,
        }

        if not config_file:
            logger.warning("No config file provided, using defaults")
            return default_config

        try:
            with open(config_file, "r") as f:
                user_config = json.load(f)

            # Update default config with user values
            default_config.update(user_config)
            logger.info(f"Loaded configuration from {config_file}")

            return default_config
        except Exception as e:
            logger.error(f"Error loading config file: {e}")
            logger.warning("Using default configuration")
            return default_config

    def run_migration(self):
        """
        Execute the full migration process

        Returns:
            Boolean indicating success status
        """
        try:
            logger.info(
                f"Starting migration from SQLite to PostgreSQL (dry run: {self.dry_run})"
            )

            # Create destination database if it doesn't exist
            self._setup_postgres_db()

            # Backup SQLite database
            self._backup_sqlite_db()

            # Check PostgreSQL setup
            if not self._check_postgres_connection():
                return False

            # Enable maintenance mode if configured
            if self.config["maintenance_mode"] and not self.dry_run:
                self._enable_maintenance_mode()

            # Get Django models and their tables
            django_tables = self._get_django_tables()

            # Run Django migrations on PostgreSQL
            self._run_django_migrations()

            # Configure connections
            sqlite_conn = self._get_sqlite_connection()
            pg_conn = self._get_postgres_connection()

            # Transfer data
            self._transfer_data(sqlite_conn, pg_conn, django_tables)

            # Set sequences
            self._set_postgres_sequences(pg_conn, django_tables)

            # Verify data
            verification_results = self._verify_migration(
                sqlite_conn, pg_conn, django_tables
            )

            # Close connections
            sqlite_conn.close()
            pg_conn.close()

            # Disable maintenance mode
            if self.config["maintenance_mode"] and not self.dry_run:
                self._disable_maintenance_mode()

            # Log summary
            self._log_migration_summary(verification_results)

            if self.dry_run:
                logger.info(
                    "Dry run completed successfully, no changes made to PostgreSQL database"
                )
            else:
                logger.info(
                    f"Migration completed successfully. {self.tables_migrated} tables and {self.rows_migrated} rows migrated."
                )

            return True

        except Exception as e:
            logger.error(f"Migration failed: {e}")

            # Attempt to disable maintenance mode if enabled
            if self.config["maintenance_mode"] and not self.dry_run:
                try:
                    self._disable_maintenance_mode()
                except Exception as inner_e:
                    logger.error(f"Failed to disable maintenance mode: {inner_e}")

            return False

    def _setup_postgres_db(self):
        """
        Set up PostgreSQL database if it doesn't exist
        """
        if self.dry_run:
            logger.info("[DRY RUN] Would create PostgreSQL database")
            return

        try:
            # Connect to PostgreSQL server (without specific database)
            conn = psycopg2.connect(
                host=self.config["pg_host"],
                port=self.config["pg_port"],
                user=self.config["pg_user"],
                password=self.config["pg_password"],
                database="postgres",  # Connect to default db first
            )
            conn.autocommit = True
            cursor = conn.cursor()

            # Check if database exists
            cursor.execute(
                f"SELECT 1 FROM pg_database WHERE datname = '{self.config['pg_dbname']}'"
            )
            exists = cursor.fetchone()

            if not exists:
                logger.info(
                    f"Creating PostgreSQL database '{self.config['pg_dbname']}'"
                )
                cursor.execute(f"CREATE DATABASE {self.config['pg_dbname']}")

                # Connect to new database to set up extensions
                conn.close()
                conn = psycopg2.connect(
                    host=self.config["pg_host"],
                    port=self.config["pg_port"],
                    user=self.config["pg_user"],
                    password=self.config["pg_password"],
                    database=self.config["pg_dbname"],
                )
                conn.autocommit = True
                cursor = conn.cursor()

                # Enable extensions
                cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis")
                cursor.execute("CREATE EXTENSION IF NOT EXISTS unaccent")

                logger.info("PostgreSQL database created and extensions enabled")
            else:
                logger.info(
                    f"PostgreSQL database '{self.config['pg_dbname']}' already exists"
                )

            cursor.close()
            conn.close()

        except Exception as e:
            logger.error(f"Failed to set up PostgreSQL database: {e}")
            raise

    def _backup_sqlite_db(self):
        """
        Create a backup of the SQLite database
        """
        try:
            # Ensure backup directory exists
            if not os.path.exists(self.config["backup_dir"]):
                os.makedirs(self.config["backup_dir"])

            # Create timestamp for backup filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(
                self.config["backup_dir"], f"sqlite_backup_{timestamp}.db"
            )

            if self.dry_run:
                logger.info(f"[DRY RUN] Would back up SQLite database to {backup_file}")
                return

            # Copy SQLite file
            sqlite_path = self.config["sqlite_db"]
            if not os.path.exists(sqlite_path):
                raise FileNotFoundError(
                    f"SQLite database file not found: {sqlite_path}"
                )

            import shutil

            shutil.copy2(sqlite_path, backup_file)

            logger.info(f"SQLite database backed up to {backup_file}")

        except Exception as e:
            logger.error(f"Failed to back up SQLite database: {e}")
            raise

    def _check_postgres_connection(self):
        """
        Verify PostgreSQL connection and settings

        Returns:
            Boolean indicating success status
        """
        try:
            # Try to connect
            conn = self._get_postgres_connection()
            cursor = conn.cursor()

            # Check version
            cursor.execute("SELECT version()")
            version = cursor.fetchone()[0]
            logger.info(f"Connected to PostgreSQL: {version}")

            # Check extensions
            cursor.execute("SELECT extname FROM pg_extension")
            extensions = [row[0] for row in cursor.fetchall()]
            logger.info(f"Available extensions: {', '.join(extensions)}")

            # Check if required extensions are present
            required_extensions = ["plpgsql", "postgis"]
            missing_extensions = [
                ext for ext in required_extensions if ext not in extensions
            ]

            if missing_extensions:
                logger.warning(
                    f"Missing required PostgreSQL extensions: {', '.join(missing_extensions)}"
                )

                if not self.dry_run:
                    for ext in missing_extensions:
                        logger.info(f"Attempting to create extension {ext}")
                        cursor.execute(f"CREATE EXTENSION IF NOT EXISTS {ext}")

                    # Verify again
                    cursor.execute("SELECT extname FROM pg_extension")
                    extensions = [row[0] for row in cursor.fetchall()]
                    still_missing = [
                        ext for ext in required_extensions if ext not in extensions
                    ]

                    if still_missing:
                        logger.error(
                            f"Failed to create extensions: {', '.join(still_missing)}"
                        )
                        return False

                    logger.info("Successfully added required extensions")

            cursor.close()
            conn.close()

            return True

        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            return False

    def _enable_maintenance_mode(self):
        """
        Enable maintenance mode for the application
        """
        try:
            # Implementation depends on how maintenance mode is configured
            # This is a placeholder for a real implementation
            logger.info("Enabling maintenance mode")

            # Example: Create a maintenance mode file
            with open("MAINTENANCE_MODE", "w") as f:
                f.write(f"Maintenance started at {datetime.now().isoformat()}")

            # Allow time for active connections to finish
            logger.info("Waiting for active connections to complete...")
            time.sleep(5)

        except Exception as e:
            logger.error(f"Failed to enable maintenance mode: {e}")
            raise

    def _disable_maintenance_mode(self):
        """
        Disable maintenance mode for the application
        """
        try:
            # Implementation depends on how maintenance mode is configured
            logger.info("Disabling maintenance mode")

            # Example: Remove maintenance mode file
            if os.path.exists("MAINTENANCE_MODE"):
                os.remove("MAINTENANCE_MODE")

        except Exception as e:
            logger.error(f"Failed to disable maintenance mode: {e}")
            raise

    def _get_django_tables(self):
        """
        Get mapping of Django models to database tables

        Returns:
            Dictionary mapping table names to model information
        """
        logger.info("Analyzing Django models and database tables")

        tables = {}
        for app_config in apps.get_app_configs():
            for model in app_config.get_models():
                if hasattr(model, "_meta"):
                    table_name = model._meta.db_table
                    pk_field = model._meta.pk.name if model._meta.pk else "id"

                    tables[table_name] = {
                        "model": model.__name__,
                        "app": app_config.name,
                        "pk_field": pk_field,
                        "has_sequence": pk_field == "id"
                        and model._meta.pk.get_internal_type()
                        in [
                            "AutoField",
                            "BigAutoField",
                            "SmallAutoField",
                            "IntegerField",
                        ],
                    }

        logger.info(f"Found {len(tables)} Django models with database tables")
        return tables

    def _run_django_migrations(self):
        """
        Run Django migrations on the PostgreSQL database
        """
        if self.dry_run:
            logger.info("[DRY RUN] Would run Django migrations on PostgreSQL")
            return

        try:
            logger.info("Running Django migrations on PostgreSQL")

            # Configure the PostgreSQL database connection
            postgres_db_config = {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": self.config["pg_dbname"],
                "USER": self.config["pg_user"],
                "PASSWORD": self.config["pg_password"],
                "HOST": self.config["pg_host"],
                "PORT": self.config["pg_port"],
            }

            # Temporarily override the database settings
            original_default_db = settings.DATABASES["default"]
            settings.DATABASES["default"] = postgres_db_config

            # Run migrations
            call_command("migrate", verbosity=1)

            # Restore original settings
            settings.DATABASES["default"] = original_default_db

            logger.info("Django migrations on PostgreSQL completed successfully")

        except Exception as e:
            logger.error(f"Failed to run Django migrations on PostgreSQL: {e}")
            raise

    def _get_sqlite_connection(self):
        """
        Get a connection to the SQLite database

        Returns:
            SQLite database connection
        """
        try:
            sqlite_path = self.config["sqlite_db"]
            conn = sqlite3.connect(sqlite_path)
            conn.row_factory = sqlite3.Row  # Return rows as dictionaries

            # Enable foreign keys
            conn.execute("PRAGMA foreign_keys = ON")

            return conn

        except Exception as e:
            logger.error(f"Failed to connect to SQLite database: {e}")
            raise

    def _get_postgres_connection(self):
        """
        Get a connection to the PostgreSQL database

        Returns:
            PostgreSQL database connection
        """
        try:
            conn = psycopg2.connect(
                host=self.config["pg_host"],
                port=self.config["pg_port"],
                user=self.config["pg_user"],
                password=self.config["pg_password"],
                database=self.config["pg_dbname"],
            )

            return conn

        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL database: {e}")
            raise

    def _transfer_data(self, sqlite_conn, pg_conn, django_tables):
        """
        Transfer data from SQLite to PostgreSQL

        Args:
            sqlite_conn: SQLite database connection
            pg_conn: PostgreSQL database connection
            django_tables: Dictionary mapping table names to model information
        """
        try:
            # Get list of tables from SQLite
            sqlite_cursor = sqlite_conn.cursor()
            sqlite_cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in sqlite_cursor.fetchall()]

            # Filter out tables to exclude
            tables = [
                table
                for table in tables
                if table not in self.config["exclude_tables"]
                and not table.startswith("sqlite_")
            ]

            logger.info(f"Preparing to transfer {len(tables)} tables")

            # Process each table
            for table in tables:
                if table in django_tables:
                    logger.info(f"Transferring table: {table}")

                    if self.dry_run:
                        logger.info(f"[DRY RUN] Would transfer data for table {table}")
                        continue

                    # Count rows
                    sqlite_cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    row_count = sqlite_cursor.fetchone()[0]

                    if row_count == 0:
                        logger.info(f"Table {table} is empty, skipping")
                        continue

                    logger.info(f"Table {table} has {row_count} rows")

                    # Get table structure
                    sqlite_cursor.execute(f"PRAGMA table_info({table})")
                    columns = [row[1] for row in sqlite_cursor.fetchall()]

                    # Clear existing data in PostgreSQL (if any)
                    pg_cursor = pg_conn.cursor()
                    pg_cursor.execute(f"TRUNCATE TABLE {table} CASCADE")

                    # Transfer in batches
                    batch_size = self.config["batch_size"]
                    offset = 0

                    while offset < row_count:
                        # Get batch of data from SQLite
                        sqlite_cursor.execute(
                            f"SELECT * FROM {table} LIMIT {batch_size} OFFSET {offset}"
                        )
                        rows = sqlite_cursor.fetchall()

                        if not rows:
                            break

                        # Prepare insert SQL
                        column_names = ", ".join(columns)
                        placeholders = ", ".join(["%s"] * len(columns))
                        insert_sql = f"INSERT INTO {table} ({column_names}) VALUES ({placeholders})"

                        # Convert rows to list of tuples for psycopg2
                        rows_data = []
                        for row in rows:
                            row_values = []
                            for col in columns:
                                value = row[col]
                                # Handle SQLite NULL values
                                if value is None:
                                    row_values.append(None)
                                else:
                                    row_values.append(value)
                            rows_data.append(tuple(row_values))

                        # Execute batch insert
                        pg_cursor.executemany(insert_sql, rows_data)
                        pg_conn.commit()

                        # Update progress
                        offset += len(rows)
                        logger.info(
                            f"Transferred {offset}/{row_count} rows for table {table}"
                        )

                        # Track total rows migrated
                        self.rows_migrated += len(rows)

                    pg_cursor.close()
                    self.tables_migrated += 1
                else:
                    logger.warning(
                        f"Table {table} not found in Django models, skipping"
                    )

            logger.info(
                f"Data transfer completed: {self.tables_migrated} tables, {self.rows_migrated} rows"
            )

        except Exception as e:
            logger.error(f"Failed to transfer data: {e}")
            if not self.dry_run:
                pg_conn.rollback()
            raise

    def _set_postgres_sequences(self, pg_conn, django_tables):
        """
        Set PostgreSQL sequences to the maximum value of each table's ID

        Args:
            pg_conn: PostgreSQL database connection
            django_tables: Dictionary mapping table names to model information
        """
        if self.dry_run:
            logger.info("[DRY RUN] Would set PostgreSQL sequences")
            return

        try:
            cursor = pg_conn.cursor()

            for table, info in django_tables.items():
                if info["has_sequence"]:
                    sequence_name = f"{table}_{info['pk_field']}_seq"

                    # Get maximum ID value
                    cursor.execute(f"SELECT MAX({info['pk_field']}) FROM {table}")
                    max_id = cursor.fetchone()[0]

                    if max_id is not None:
                        # Set sequence to max_id + 1
                        cursor.execute(f"SELECT setval('{sequence_name}', {max_id})")
                        logger.info(f"Set sequence {sequence_name} to {max_id}")
                    else:
                        logger.info(
                            f"Table {table} is empty, sequence {sequence_name} not modified"
                        )

            pg_conn.commit()
            cursor.close()

            logger.info("PostgreSQL sequences updated successfully")

        except Exception as e:
            logger.error(f"Failed to set PostgreSQL sequences: {e}")
            if not self.dry_run:
                pg_conn.rollback()
            raise

    def _verify_migration(self, sqlite_conn, pg_conn, django_tables):
        """
        Verify the migration by comparing row counts and sample data

        Args:
            sqlite_conn: SQLite database connection
            pg_conn: PostgreSQL database connection
            django_tables: Dictionary mapping table names to model information

        Returns:
            Dictionary with verification results
        """
        try:
            logger.info("Verifying migration")

            verification_results = {
                "tables_checked": 0,
                "tables_matched": 0,
                "tables_mismatched": 0,
                "details": {},
            }

            sqlite_cursor = sqlite_conn.cursor()
            pg_cursor = pg_conn.cursor()

            for table in django_tables:
                logger.info(f"Verifying table: {table}")

                # Compare row counts
                sqlite_cursor.execute(f"SELECT COUNT(*) FROM {table}")
                sqlite_count = sqlite_cursor.fetchone()[0]

                pg_cursor.execute(f"SELECT COUNT(*) FROM {table}")
                pg_count = pg_cursor.fetchone()[0]

                count_match = sqlite_count == pg_count

                # Get column names
                sqlite_cursor.execute(f"PRAGMA table_info({table})")
                sqlite_columns = [row[1] for row in sqlite_cursor.fetchall()]

                pg_cursor.execute(
                    f"""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = '{table}' ORDER BY ordinal_position
                """
                )
                pg_columns = [row[0] for row in pg_cursor.fetchall()]

                # Check if table has rows for detailed verification
                has_rows = sqlite_count > 0

                # For tables with rows, check a sample
                sample_matches = None
                if has_rows:
                    # Get common columns
                    common_columns = [
                        col
                        for col in sqlite_columns
                        if col.lower() in [c.lower() for c in pg_columns]
                    ]
                    column_list = ", ".join(common_columns)

                    # Get primary key
                    pk_field = django_tables[table]["pk_field"]

                    # Check a sample of records
                    sample_size = min(10, sqlite_count)

                    # Get random sample from SQLite
                    sqlite_cursor.execute(
                        f"SELECT {column_list} FROM {table} ORDER BY {pk_field} LIMIT {sample_size}"
                    )
                    sqlite_sample = sqlite_cursor.fetchall()

                    # Convert to a set of tuples for comparison
                    sqlite_sample_set = set()
                    for row in sqlite_sample:
                        row_values = tuple(row[col] for col in common_columns)
                        sqlite_sample_set.add(row_values)

                    # Check if records exist in PostgreSQL
                    pg_matches = 0
                    for row in sqlite_sample:
                        # Build WHERE clause for this record
                        conditions = []
                        params = []

                        for col in common_columns:
                            if row[col] is None:
                                conditions.append(f"{col} IS NULL")
                            else:
                                conditions.append(f"{col} = %s")
                                params.append(row[col])

                        where_clause = " AND ".join(conditions)

                        # Check if record exists
                        pg_cursor.execute(
                            f"SELECT 1 FROM {table} WHERE {where_clause} LIMIT 1",
                            params,
                        )
                        if pg_cursor.fetchone():
                            pg_matches += 1

                    # Check if all samples were found
                    sample_matches = pg_matches == sample_size

                # Record results
                verification_results["tables_checked"] += 1

                table_result = {
                    "row_count_match": count_match,
                    "sqlite_count": sqlite_count,
                    "pg_count": pg_count,
                    "has_rows": has_rows,
                    "sample_matches": sample_matches,
                }

                verification_results["details"][table] = table_result

                if count_match and (not has_rows or sample_matches):
                    verification_results["tables_matched"] += 1
                    logger.info(f"Table {table} verified: counts match ({pg_count})")
                else:
                    verification_results["tables_mismatched"] += 1
                    if not count_match:
                        logger.warning(
                            f"Table {table} verification failed: count mismatch (SQLite: {sqlite_count}, PostgreSQL: {pg_count})"
                        )
                    elif not sample_matches:
                        logger.warning(
                            f"Table {table} verification failed: sample data mismatch"
                        )

            pg_cursor.close()
            sqlite_cursor.close()

            return verification_results

        except Exception as e:
            logger.error(f"Failed to verify migration: {e}")
            return {
                "error": str(e),
                "tables_checked": 0,
                "tables_matched": 0,
                "tables_mismatched": 0,
                "details": {},
            }

    def _log_migration_summary(self, verification_results):
        """
        Log a summary of the migration results

        Args:
            verification_results: Dictionary with verification results
        """
        duration = datetime.now() - self.started_at
        duration_str = str(duration).split(".")[0]  # Remove microseconds

        logger.info("Migration Summary:")
        logger.info(f"Duration: {duration_str}")
        logger.info(f"Tables Migrated: {self.tables_migrated}")
        logger.info(f"Rows Migrated: {self.rows_migrated}")
        logger.info(f"Errors: {self.errors}")

        if verification_results:
            logger.info("Verification Results:")
            logger.info(f"Tables Checked: {verification_results['tables_checked']}")
            logger.info(f"Tables Matched: {verification_results['tables_matched']}")
            logger.info(
                f"Tables Mismatched: {verification_results['tables_mismatched']}"
            )

            if verification_results["tables_mismatched"] > 0:
                logger.warning("Mismatched Tables:")
                for table, result in verification_results["details"].items():
                    if not result["row_count_match"] or (
                        result["has_rows"] and not result["sample_matches"]
                    ):
                        logger.warning(
                            f"  - {table} (SQLite: {result['sqlite_count']}, PostgreSQL: {result['pg_count']})"
                        )


def main():
    parser = argparse.ArgumentParser(description="Migrate from SQLite to PostgreSQL")
    parser.add_argument(
        "--dry-run", action="store_true", help="Test migration without making changes"
    )
    parser.add_argument("--config", help="Path to configuration file")
    args = parser.parse_args()

    migration = DatabaseMigration(config_file=args.config, dry_run=args.dry_run)
    success = migration.run_migration()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
