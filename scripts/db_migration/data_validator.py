#!/usr/bin/env python
# =============================================================================
# Queue Me Data Validator
# Sophisticated data integrity verification and cross-reference checking
# =============================================================================

import argparse
import concurrent.futures
import json
import logging
import os
import sqlite3
import sys
from datetime import datetime

import django
import psycopg2
from django.apps import apps
from tabulate import tabulate

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
        logging.FileHandler(os.path.join(BASE_DIR, "data_validation.log")),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


class DataValidator:
    def __init__(self, sqlite_path, pg_config, report_file=None):
        """Initialize the validator with database connections and settings"""
        self.sqlite_path = sqlite_path
        self.pg_config = pg_config
        self.report_file = report_file or os.path.join(
            os.path.dirname(__file__), "validation_report.json"
        )

        # Connect to databases
        self.sqlite_conn = None
        self.pg_conn = None

        # Results tracking
        self.validation_results = {
            "timestamp": datetime.now().isoformat(),
            "source_db": sqlite_path,
            "target_db": f"{pg_config['host']}:{pg_config['port']}/{pg_config['dbname']}",
            "tables": {},
            "foreign_keys": [],
            "summary": {
                "total_tables": 0,
                "passed_tables": 0,
                "failed_tables": 0,
                "total_rows": 0,
                "matching_rows": 0,
                "missing_rows": 0,
                "fk_violations": 0,
            },
        }

    def connect(self):
        """Connect to both databases"""
        logger.info("Connecting to databases...")
        try:
            self.sqlite_conn = sqlite3.connect(self.sqlite_path)
            self.sqlite_conn.row_factory = sqlite3.Row

            self.pg_conn = psycopg2.connect(**self.pg_config)

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
        """Get all tables from SQLite that should be in PostgreSQL"""
        cursor = self.sqlite_conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [
            table[0]
            for table in cursor.fetchall()
            if table[0] != "sqlite_sequence" and not table[0].startswith("django_migrations")
        ]
        cursor.close()
        return tables

    def get_table_columns(self, table_name, is_sqlite=True):
        """Get column names for a table"""
        if is_sqlite:
            cursor = self.sqlite_conn.cursor()
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = [col[1] for col in cursor.fetchall()]
            cursor.close()
        else:
            cursor = self.pg_conn.cursor()
            cursor.execute(
                f"""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = '{table_name}'
                ORDER BY ordinal_position;
            """
            )
            columns = [col[0] for col in cursor.fetchall()]
            cursor.close()

        return columns

    def validate_table_structure(self, table_name):
        """Validate table structure between SQLite and PostgreSQL"""
        sqlite_columns = set(self.get_table_columns(table_name, is_sqlite=True))
        pg_columns = set(self.get_table_columns(table_name, is_sqlite=False))

        missing_columns = sqlite_columns - pg_columns
        extra_columns = pg_columns - sqlite_columns

        return {
            "table": table_name,
            "sqlite_columns": len(sqlite_columns),
            "pg_columns": len(pg_columns),
            "matching_columns": len(sqlite_columns.intersection(pg_columns)),
            "missing_columns": list(missing_columns),
            "extra_columns": list(extra_columns),
            "structure_match": len(missing_columns) == 0,
        }

    def validate_row_counts(self, table_name):
        """Validate row counts between SQLite and PostgreSQL"""
        sqlite_cursor = self.sqlite_conn.cursor()
        sqlite_cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
        sqlite_count = sqlite_cursor.fetchone()[0]
        sqlite_cursor.close()

        pg_cursor = self.pg_conn.cursor()
        pg_cursor.execute(f'SELECT COUNT(*) FROM "{table_name}";')
        pg_count = pg_cursor.fetchone()[0]
        pg_cursor.close()

        return {
            "table": table_name,
            "sqlite_count": sqlite_count,
            "pg_count": pg_count,
            "count_match": sqlite_count == pg_count,
            "difference": abs(sqlite_count - pg_count),
        }

    def validate_sample_data(self, table_name, sample_size=5):
        """Validate a sample of data between SQLite and PostgreSQL"""
        # Get common columns
        sqlite_columns = self.get_table_columns(table_name, is_sqlite=True)
        pg_columns = self.get_table_columns(table_name, is_sqlite=False)
        common_columns = [col for col in sqlite_columns if col in pg_columns]

        if not common_columns:
            return {
                "table": table_name,
                "error": "No common columns to compare",
                "samples_validated": 0,
                "data_match": False,
            }

        # Get ID column name (usually 'id')
        id_column = "id" if "id" in common_columns else common_columns[0]

        # Get sample rows from SQLite
        sqlite_cursor = self.sqlite_conn.cursor()
        sqlite_cursor.execute(
            f"SELECT {id_column} FROM {table_name} ORDER BY {id_column} LIMIT {sample_size};"
        )
        sample_ids = [row[0] for row in sqlite_cursor.fetchall()]
        sqlite_cursor.close()

        if not sample_ids:
            return {
                "table": table_name,
                "error": "No rows found in SQLite",
                "samples_validated": 0,
                "data_match": True,  # Empty tables match
            }

        # Compare data for each sample row
        mismatches = []
        matched = 0

        for row_id in sample_ids:
            # Get SQLite row
            sqlite_cursor = self.sqlite_conn.cursor()
            cols_str = ", ".join(common_columns)
            sqlite_cursor.execute(
                f"SELECT {cols_str} FROM {table_name} WHERE {id_column} = ?;", (row_id,)
            )
            sqlite_row = dict(sqlite_cursor.fetchone())
            sqlite_cursor.close()

            # Get PostgreSQL row
            pg_cursor = self.pg_conn.cursor()
            cols_str = ", ".join([f'"{col}"' for col in common_columns])
            pg_cursor.execute(
                f'SELECT {cols_str} FROM "{table_name}" WHERE "{id_column}" = %s;',
                (row_id,),
            )
            pg_row_tuple = pg_cursor.fetchone()
            pg_cursor.close()

            if not pg_row_tuple:
                mismatches.append({"id": row_id, "error": "Row not found in PostgreSQL"})
                continue

            # Convert PostgreSQL row to dict
            pg_row = {}
            for i, col in enumerate(common_columns):
                if i < len(pg_row_tuple):
                    pg_row[col] = pg_row_tuple[i]

            # Compare values
            row_mismatches = []
            for col in common_columns:
                if col in sqlite_row and col in pg_row:
                    sqlite_val = sqlite_row[col]
                    pg_val = pg_row[col]

                    # Handle None/NULL values
                    if sqlite_val is None and pg_val is None:
                        continue

                    # Compare as strings to handle different types
                    if str(sqlite_val) != str(pg_val):
                        row_mismatches.append(
                            {
                                "column": col,
                                "sqlite_value": sqlite_val,
                                "pg_value": pg_val,
                            }
                        )

            if row_mismatches:
                mismatches.append({"id": row_id, "mismatched_columns": row_mismatches})
            else:
                matched += 1

        return {
            "table": table_name,
            "samples_validated": len(sample_ids),
            "matched_samples": matched,
            "mismatched_samples": len(sample_ids) - matched,
            "data_match": matched == len(sample_ids),
            "mismatches": mismatches,
        }

    def validate_foreign_keys(self):
        """Validate foreign key constraints in PostgreSQL"""
        logger.info("Validating foreign key constraints...")

        # Get Django models and their relations
        app_configs = apps.get_app_configs()
        models = []

        for app in app_configs:
            models.extend(app.get_models())

        fk_violations = []

        for model in models:
            table_name = model._meta.db_table

            # Check each foreign key
            for field in model._meta.fields:
                if (
                    field.is_relation
                    and field.remote_field.model != model
                    and hasattr(field, "column")
                ):
                    fk_column = field.column
                    fk_table = field.remote_field.model._meta.db_table
                    fk_field = field.remote_field.model._meta.pk.column

                    # Check for orphaned foreign keys
                    query = f"""
                        SELECT t1."{fk_column}", COUNT(*)
                        FROM "{table_name}" t1
                        LEFT JOIN "{fk_table}" t2 ON t1."{fk_column}" = t2."{fk_field}"
                        WHERE t1."{fk_column}" IS NOT NULL AND t2."{fk_field}" IS NULL
                        GROUP BY t1."{fk_column}";
                    """

                    try:
                        pg_cursor = self.pg_conn.cursor()
                        pg_cursor.execute(query)
                        violations = pg_cursor.fetchall()
                        pg_cursor.close()

                        if violations:
                            for violation in violations:
                                fk_violations.append(
                                    {
                                        "table": table_name,
                                        "fk_column": fk_column,
                                        "fk_table": fk_table,
                                        "fk_value": violation[0],
                                        "violation_count": violation[1],
                                    }
                                )
                    except Exception as e:
                        logger.warning(
                            f"Could not check FK constraint {table_name}.{fk_column}: {str(e)}"
                        )

        return fk_violations

    def validate_table(self, table_name):
        """Run all validations for a single table"""
        logger.info(f"Validating table: {table_name}")

        structure_result = self.validate_table_structure(table_name)
        count_result = self.validate_row_counts(table_name)
        data_result = self.validate_sample_data(table_name)

        # Determine pass/fail status
        passed = (
            structure_result["structure_match"]
            and count_result["count_match"]
            and data_result["data_match"]
        )

        # Update overall statistics
        self.validation_results["summary"]["total_tables"] += 1
        if passed:
            self.validation_results["summary"]["passed_tables"] += 1
        else:
            self.validation_results["summary"]["failed_tables"] += 1

        self.validation_results["summary"]["total_rows"] += count_result["sqlite_count"]
        self.validation_results["summary"]["matching_rows"] += (
            count_result["pg_count"]
            if count_result["count_match"]
            else count_result["sqlite_count"] - count_result["difference"]
        )
        self.validation_results["summary"]["missing_rows"] += (
            0 if count_result["count_match"] else count_result["difference"]
        )

        # Store detailed results
        self.validation_results["tables"][table_name] = {
            "structure": structure_result,
            "count": count_result,
            "data": data_result,
            "passed": passed,
        }

        return passed

    def generate_report(self):
        """Generate a JSON report file with all validation results"""
        # Add foreign key validation results
        self.validation_results["summary"]["fk_violations"] = len(
            self.validation_results["foreign_keys"]
        )

        # Write to file
        with open(self.report_file, "w") as f:
            json.dump(self.validation_results, f, indent=2)

        logger.info(f"Validation report saved to {self.report_file}")

        # Print summary
        summary = self.validation_results["summary"]
        print("\n=== Validation Summary ===")
        print(f"Total tables validated: {summary['total_tables']}")
        print(
            f"Passed tables: {summary['passed_tables']} ({(summary['passed_tables']/summary['total_tables']*100):.1f}%)"
        )
        print(f"Failed tables: {summary['failed_tables']}")
        print(f"Total rows checked: {summary['total_rows']}")
        print(
            f"Matching rows: {summary['matching_rows']} ({(summary['matching_rows']/summary['total_rows']*100 if summary['total_rows'] else 0):.1f}%)"
        )
        print(f"Missing/mismatched rows: {summary['missing_rows']}")
        print(f"Foreign key violations: {summary['fk_violations']}")

        # Print table results
        table_data = []
        for table_name, result in self.validation_results["tables"].items():
            status = "✅ Pass" if result["passed"] else "❌ Fail"
            cols_match = "✅" if result["structure"]["structure_match"] else "❌"
            count_match = "✅" if result["count"]["count_match"] else "❌"
            data_match = "✅" if result["data"]["data_match"] else "❌"

            table_data.append(
                [
                    table_name,
                    status,
                    f"{result['count']['pg_count']}/{result['count']['sqlite_count']}",
                    cols_match,
                    count_match,
                    data_match,
                ]
            )

        print("\n=== Table Results ===")
        print(
            tabulate(
                table_data,
                headers=[
                    "Table",
                    "Status",
                    "Rows (PG/SQLite)",
                    "Structure",
                    "Count",
                    "Data",
                ],
                tablefmt="grid",
            )
        )

        # Print FK violations if any
        if self.validation_results["foreign_keys"]:
            fk_data = []
            for violation in self.validation_results["foreign_keys"][:10]:  # Show top 10
                fk_data.append(
                    [
                        violation["table"],
                        f"{violation['fk_column']} -> {violation['fk_table']}",
                        violation["fk_value"],
                        violation["violation_count"],
                    ]
                )

            print("\n=== Foreign Key Violations (Top 10) ===")
            print(
                tabulate(
                    fk_data,
                    headers=["Table", "Relation", "Value", "Count"],
                    tablefmt="grid",
                )
            )

            if len(self.validation_results["foreign_keys"]) > 10:
                print(
                    f"... and {len(self.validation_results['foreign_keys']) - 10} more violations. See report file for details."
                )

    def validate(self):
        """Run the full validation process"""
        logger.info("Starting data validation...")

        if not self.connect():
            return False

        try:
            # Get tables to validate
            tables = self.get_all_tables()
            logger.info(f"Found {len(tables)} tables to validate.")

            # Validate each table
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                futures = {executor.submit(self.validate_table, table): table for table in tables}
                for future in concurrent.futures.as_completed(futures):
                    table = futures[future]
                    try:
                        future.result()
                    except Exception as e:
                        logger.error(f"Error validating table {table}: {str(e)}")

            # Validate foreign keys
            self.validation_results["foreign_keys"] = self.validate_foreign_keys()

            # Generate report
            self.generate_report()

            return self.validation_results["summary"]["failed_tables"] == 0

        finally:
            self.close()


def main():
    parser = argparse.ArgumentParser(description="Validate data between SQLite and PostgreSQL.")
    parser.add_argument("--sqlite-path", default="db.sqlite3", help="Path to SQLite database file")
    parser.add_argument(
        "--report", default="validation_report.json", help="Path to output report file"
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

    # Create validator and run validation
    validator = DataValidator(
        sqlite_path=args.sqlite_path, pg_config=pg_config, report_file=args.report
    )

    success = validator.validate()

    if success:
        logger.info("Validation completed successfully! All tables match.")
        return 0
    else:
        logger.warning("Validation completed with mismatches. See report for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
