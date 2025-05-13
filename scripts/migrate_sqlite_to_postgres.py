#!/usr/bin/env python3
"""
SQLite to PostgreSQL Migration Script

This script migrates data from a SQLite database to PostgreSQL for the Queue Me project.
It handles relationships properly, preserving primary keys and foreign key relationships.

Usage:
    python scripts/migrate_sqlite_to_postgres.py [--no-prompt]

Options:
    --no-prompt  Skip confirmation prompts
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import django

# Add project directory to path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

# Set Django settings module to use SQLite
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "queueme.settings.development")
os.environ["USE_SQLITE"] = "True"  # Force SQLite for data extraction

try:
    django.setup()
except Exception as e:
    print(f"Error setting up Django with SQLite: {e}")
    sys.exit(1)

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection

from utils.constants import DATABASE_MIGRATION_CHUNK_SIZE

# Check if both databases are configured
if "sqlite" not in settings.DATABASES["default"]["ENGINE"]:
    print("Source database is not SQLite. Please set USE_SQLITE=True")
    sys.exit(1)

# Parse arguments
parser = argparse.ArgumentParser(description="Migrate data from SQLite to PostgreSQL")
parser.add_argument("--no-prompt", action="store_true", help="Skip confirmation prompts")
args = parser.parse_args()

# Constants
CHUNK_SIZE = DATABASE_MIGRATION_CHUNK_SIZE
SQLITE_DB_PATH = os.path.join(BASE_DIR, "db.sqlite3")
DUMP_DIR = os.path.join(BASE_DIR, "db", "migration_dumps")
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
DUMP_FILE_PREFIX = f"{DUMP_DIR}/sqlite_dump_{TIMESTAMP}"


def ensure_directory_exists(directory):
    """Ensure the target directory exists"""
    if not os.path.exists(directory):
        os.makedirs(directory)
        print(f"Created directory: {directory}")


def backup_sqlite_db():
    """Create a backup of the SQLite database"""
    backup_path = f"{SQLITE_DB_PATH}.backup_{TIMESTAMP}"
    print(f"Creating SQLite backup at {backup_path}...")

    try:
        import shutil

        shutil.copy2(SQLITE_DB_PATH, backup_path)
        print(f"Backup created successfully at {backup_path}")
        return True
    except Exception as e:
        print(f"Error creating backup: {e}")
        return False


def get_model_dependencies():
    """
    Generate a dependency order for models to handle foreign key relationships properly.
    This uses a simple topological sort.
    """
    models = []
    app_configs = apps.get_app_configs()

    # Collect all models
    for app_config in app_configs:
        if app_config.name.startswith("django.") or app_config.name.startswith("rest_framework"):
            continue

        for model in app_config.get_models():
            # Skip proxy models
            if model._meta.proxy:
                continue

            models.append(model)

    # Sort models based on dependencies
    model_dependencies = {}

    for model in models:
        dependencies = set()

        for field in model._meta.fields:
            if field.remote_field and field.remote_field.model:
                dependencies.add(field.remote_field.model)

        model_dependencies[model] = dependencies

    # Topological sort
    sorted_models = []
    visited = set()

    def visit(model):
        if model in visited:
            return

        visited.add(model)

        for dependency in model_dependencies.get(model, []):
            if dependency in model_dependencies:  # Only visit if it's our managed models
                visit(dependency)

        sorted_models.append(model)

    for model in models:
        visit(model)

    return sorted_models


def extract_data_from_sqlite():
    """Extract data from SQLite database into JSON files"""
    ensure_directory_exists(DUMP_DIR)

    print("Analyzing model dependencies...")
    models = get_model_dependencies()

    print(f"Found {len(models)} models to migrate")
    data_stats = {}

    for model in models:
        model_name = f"{model._meta.app_label}.{model._meta.model_name}"
        print(f"Extracting data from {model_name}...")

        queryset = model.objects.all()
        count = queryset.count()
        data_stats[model_name] = count

        if count == 0:
            print(f"  No data found for {model_name}, skipping")
            continue

        # Handle large tables with chunking
        file_index = 0
        for offset in range(0, count, CHUNK_SIZE):
            chunk = queryset[offset : offset + CHUNK_SIZE]
            records = []

            for obj in chunk:
                record = {}
                for field in model._meta.fields:
                    field_name = field.name
                    field_value = getattr(obj, field_name)

                    # Handle special field types
                    if field_value is not None:
                        if isinstance(field_value, (datetime, date)):
                            field_value = field_value.isoformat()
                        elif hasattr(field_value, "pk"):
                            field_value = field_value.pk

                    record[field_name] = field_value
                records.append(record)

            # Write chunk to file
            filename = f"{DUMP_FILE_PREFIX}_{model._meta.app_label}_{model._meta.model_name}_{file_index}.json"
            with open(filename, "w") as f:
                json.dump(records, f, ensure_ascii=False, indent=2)

            print(f"  Exported {len(records)} records to {filename}")
            file_index += 1

    # Write data statistics for verification
    with open(f"{DUMP_FILE_PREFIX}_stats.json", "w") as f:
        json.dump(data_stats, f, indent=2)

    print(
        f"Data extraction complete. Total models: {len(models)}, total records: {sum(data_stats.values())}"
    )
    return data_stats


def configure_postgres():
    """Configure PostgreSQL settings and validate connection"""
    # Unset the SQLite environment variable to use PostgreSQL settings
    if "USE_SQLITE" in os.environ:
        del os.environ["USE_SQLITE"]

    # Reset Django to use PostgreSQL settings
    django.setup()

    # Validate PostgreSQL connection
    try:
        from django.db import connections

        cursor = connections["default"].cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"Connected to PostgreSQL: {version}")
        return True
    except Exception as e:
        print(f"Error connecting to PostgreSQL: {e}")
        return False


def load_data_into_postgres():
    """Load data from JSON files into PostgreSQL"""
    print("Loading data into PostgreSQL...")

    # Get stats file to process models in the same order
    stats_file = f"{DUMP_FILE_PREFIX}_stats.json"
    if not os.path.exists(stats_file):
        print(f"Stats file not found: {stats_file}")
        return False

    with open(stats_file, "r") as f:
        data_stats = json.load(f)

    # Process each model
    for model_name, count in data_stats.items():
        if count == 0:
            continue

        app_label, model_label = model_name.split(".")
        model = apps.get_model(app_label, model_label)
        print(f"Loading data for {model_name}...")

        # Find all chunks for this model
        chunk_files = [
            f
            for f in os.listdir(DUMP_DIR)
            if f.startswith(f"sqlite_dump_{TIMESTAMP}_{app_label}_{model_label}_")
            and f.endswith(".json")
        ]

        for chunk_file in sorted(chunk_files):
            file_path = os.path.join(DUMP_DIR, chunk_file)
            print(f"  Processing {file_path}...")

            with open(file_path, "r") as f:
                records = json.load(f)

            # Process records in smaller batches for memory efficiency
            batch_size = 100
            for i in range(0, len(records), batch_size):
                batch = records[i : i + batch_size]

                # Use bulk_create with handling for primary keys
                objects = []
                for record in batch:
                    obj = model()
                    for field_name, field_value in record.items():
                        setattr(obj, field_name, field_value)
                    objects.append(obj)

                try:
                    model.objects.bulk_create(objects, ignore_conflicts=True)
                    print(f"    Imported {len(objects)} records")
                except Exception as e:
                    print(f"    Error importing batch: {e}")
                    # Fall back to individual inserts on error
                    for record in batch:
                        try:
                            obj = model()
                            for field_name, field_value in record.items():
                                setattr(obj, field_name, field_value)
                            obj.save()
                        except Exception as inner_e:
                            print(f"      Error importing record: {inner_e}")

    print("Data import complete")
    return True


def main():
    """Main migration function"""
    print("=" * 80)
    print("Queue Me: SQLite to PostgreSQL Migration Tool")
    print("=" * 80)

    # Check if SQLite database exists
    if not os.path.exists(SQLITE_DB_PATH):
        print(f"SQLite database not found at {SQLITE_DB_PATH}")
        sys.exit(1)

    # Confirm migration if not using --no-prompt
    if not args.no_prompt:
        print("\nWARNING: This will migrate data from SQLite to PostgreSQL.")
        print("Make sure PostgreSQL is properly configured in your .env file.")
        print("The process will:")
        print("1. Create a backup of your SQLite database")
        print("2. Extract all data from SQLite to JSON files")
        print("3. Configure PostgreSQL connection")
        print("4. Load all data into PostgreSQL\n")

        confirm = input("Continue? (y/n): ")
        if confirm.lower() != "y":
            print("Migration aborted.")
            sys.exit(0)

    # Create SQLite backup
    if not backup_sqlite_db():
        print("Backup failed. Aborting migration.")
        sys.exit(1)

    # Extract data from SQLite
    print("\nExtracting data from SQLite...")
    data_stats = extract_data_from_sqlite()
    total_records = sum(data_stats.values())

    # Configure PostgreSQL
    print("\nConfiguring PostgreSQL...")
    if not configure_postgres():
        print("PostgreSQL configuration failed. Aborting migration.")
        sys.exit(1)

    # Migrate data to PostgreSQL
    print("\nMigrating data to PostgreSQL...")
    if load_data_into_postgres():
        print("\nMigration completed successfully!")
        print(f"Total records migrated: {total_records}")
        print(f"Data dump files are in: {DUMP_DIR}")
        print(f"SQLite backup: {SQLITE_DB_PATH}.backup_{TIMESTAMP}")
    else:
        print("\nMigration failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
