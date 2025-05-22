#!/usr/bin/env python
"""
Database Backup Script for QueueMe

This script performs database backups with the following features:
1. Full PostgreSQL database dump
2. Backup rotation with daily, weekly, and monthly retention
3. Backup verification
4. Compression
5. Optional cloud storage (AWS S3, Google Cloud Storage) upload
6. Notification on backup completion or failure
"""

import argparse
import gzip
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from configparser import ConfigParser
from datetime import datetime, timedelta

import boto3
from google.cloud import storage

# Add Django project to path for imports and config access
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_DIR)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(PROJECT_DIR, "logs", "database_backup.log")),
    ],
)
logger = logging.getLogger("database_backup")

# Configuration defaults
DEFAULT_CONFIG = {
    "backup_dir": os.path.join(PROJECT_DIR, "backups"),
    "retention": {
        "daily": 7,  # Keep daily backups for 7 days
        "weekly": 4,  # Keep weekly backups for 4 weeks
        "monthly": 12,  # Keep monthly backups for 12 months
    },
    "compression": True,
    "storage": {"local": True, "s3": False, "gcs": False},
    "notify": True,
}


def load_config(config_file=None):
    """Load backup configuration"""
    config = DEFAULT_CONFIG.copy()

    # If a config file is specified, load it
    if config_file and os.path.exists(config_file):
        try:
            parser = ConfigParser()
            parser.read(config_file)

            # Parse storage settings
            if parser.has_section("storage"):
                config["storage"]["local"] = parser.getboolean(
                    "storage", "local", fallback=True
                )
                config["storage"]["s3"] = parser.getboolean(
                    "storage", "s3", fallback=False
                )
                config["storage"]["gcs"] = parser.getboolean(
                    "storage", "gcs", fallback=False
                )

                if config["storage"]["s3"]:
                    config["storage"]["s3_bucket"] = parser.get(
                        "storage", "s3_bucket", fallback="queueme-backups"
                    )
                    config["storage"]["s3_prefix"] = parser.get(
                        "storage", "s3_prefix", fallback="db-backups/"
                    )
                    config["storage"]["s3_region"] = parser.get(
                        "storage", "s3_region", fallback="us-east-1"
                    )

                if config["storage"]["gcs"]:
                    config["storage"]["gcs_bucket"] = parser.get(
                        "storage", "gcs_bucket", fallback="queueme-backups"
                    )
                    config["storage"]["gcs_prefix"] = parser.get(
                        "storage", "gcs_prefix", fallback="db-backups/"
                    )

            # Parse backup directory
            if parser.has_section("backup"):
                config["backup_dir"] = parser.get(
                    "backup", "directory", fallback=config["backup_dir"]
                )
                config["compression"] = parser.getboolean(
                    "backup", "compression", fallback=True
                )

            # Parse retention settings
            if parser.has_section("retention"):
                config["retention"]["daily"] = parser.getint(
                    "retention", "daily", fallback=7
                )
                config["retention"]["weekly"] = parser.getint(
                    "retention", "weekly", fallback=4
                )
                config["retention"]["monthly"] = parser.getint(
                    "retention", "monthly", fallback=12
                )

            # Parse notification settings
            if parser.has_section("notify"):
                config["notify"] = parser.getboolean("notify", "enabled", fallback=True)
                if config["notify"]:
                    config["notify_email"] = parser.get(
                        "notify", "email", fallback=None
                    )
                    config["notify_slack"] = parser.get(
                        "notify", "slack_webhook", fallback=None
                    )

        except Exception as e:
            logger.error(f"Error loading config file: {str(e)}")
            logger.info("Using default configuration")

    # Ensure backup directory exists
    os.makedirs(config["backup_dir"], exist_ok=True)

    # Create subdirectories for backup types
    for backup_type in ["daily", "weekly", "monthly"]:
        os.makedirs(os.path.join(config["backup_dir"], backup_type), exist_ok=True)

    return config


def get_database_config():
    """Get database connection parameters from Django settings or environment"""
    try:
        # Try to load from Django settings
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "queueme.settings")
        import django

        django.setup()
        from django.conf import settings

        db_config = settings.DATABASES["default"]

        return {
            "name": db_config["NAME"],
            "user": db_config["USER"],
            "password": db_config["PASSWORD"],
            "host": db_config["HOST"],
            "port": db_config["PORT"],
        }
    except Exception as e:
        logger.warning(f"Could not load database config from Django settings: {str(e)}")

        # Fallback to environment variables
        return {
            "name": os.environ.get("DB_NAME", "queueme"),
            "user": os.environ.get("DB_USER", "postgres"),
            "password": os.environ.get("DB_PASSWORD", ""),
            "host": os.environ.get("DB_HOST", "localhost"),
            "port": os.environ.get("DB_PORT", "5432"),
        }


def create_backup(db_config, backup_dir, compress=True):
    """
    Create a database backup using pg_dump

    Args:
        db_config: Database configuration dictionary
        backup_dir: Directory to store backup
        compress: Whether to compress the backup with gzip

    Returns:
        Tuple of (success, backup_path, error_message)
    """
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    filename = f"queueme_backup_{timestamp}.sql"
    backup_path = os.path.join(backup_dir, filename)

    # Setup environment variables for pg_dump
    env = os.environ.copy()
    if db_config["password"]:
        env["PGPASSWORD"] = db_config["password"]

    # Prepare pg_dump command
    pg_dump_cmd = [
        "pg_dump",
        "-h",
        db_config["host"],
        "-p",
        db_config["port"],
        "-U",
        db_config["user"],
        "-d",
        db_config["name"],
        "-F",
        "c",  # Custom format for better restoration
        "-b",  # Include large objects
        "-v",  # Verbose mode
        "-f",
        backup_path,
    ]

    try:
        # Execute pg_dump
        logger.info(f"Starting database backup to {backup_path}")
        start_time = time.time()

        result = subprocess.run(
            pg_dump_cmd,
            env=env,
            check=True,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )

        elapsed_time = time.time() - start_time

        # Check if backup file exists and has content
        if not os.path.exists(backup_path) or os.path.getsize(backup_path) == 0:
            error_msg = "Backup file not created or is empty"
            logger.error(error_msg)
            return False, None, error_msg

        logger.info(f"Database backup completed in {elapsed_time:.2f} seconds")

        # Compress if requested
        if compress:
            compressed_path = f"{backup_path}.gz"
            logger.info(f"Compressing backup to {compressed_path}")

            with open(backup_path, "rb") as f_in:
                with gzip.open(compressed_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)

            # Remove original uncompressed file
            os.remove(backup_path)
            backup_path = compressed_path
            logger.info("Compression completed")

        # Calculate file hash for verification
        file_hash = calculate_file_hash(backup_path)

        # Create a metadata file
        metadata = {
            "database": db_config["name"],
            "timestamp": now.isoformat(),
            "size": os.path.getsize(backup_path),
            "compressed": compress,
            "sha256": file_hash,
            "command": " ".join(pg_dump_cmd),
            "hostname": os.uname().nodename,
        }

        metadata_path = f"{backup_path}.meta.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        return True, backup_path, None

    except subprocess.CalledProcessError as e:
        error_msg = f"pg_dump error: {e.stderr.decode()}"
        logger.error(error_msg)
        return False, None, error_msg
    except Exception as e:
        error_msg = f"Backup error: {str(e)}"
        logger.error(error_msg)
        return False, None, error_msg


def verify_backup(backup_path):
    """
    Verify the backup file is valid by attempting to list its contents

    Args:
        backup_path: Path to the backup file

    Returns:
        Tuple of (success, error_message)
    """
    # If backup is compressed, decompress to temp file first
    is_compressed = backup_path.endswith(".gz")

    if is_compressed:
        try:
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            with gzip.open(backup_path, "rb") as f_in:
                with open(temp_file.name, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)

            verify_path = temp_file.name
        except Exception as e:
            error_msg = f"Error decompressing backup for verification: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    else:
        verify_path = backup_path

    try:
        # Try to list contents of the backup
        cmd = ["pg_restore", "-l", verify_path]
        result = subprocess.run(
            cmd, check=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE
        )

        # Check if we got a table of contents
        if result.stdout:
            logger.info("Backup verification successful")
            return True, None
        else:
            error_msg = "Empty backup content listing"
            logger.error(error_msg)
            return False, error_msg

    except subprocess.CalledProcessError as e:
        error_msg = f"Backup verification failed: {e.stderr.decode()}"
        logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Backup verification error: {str(e)}"
        logger.error(error_msg)
        return False, error_msg
    finally:
        # Clean up temp file if used
        if is_compressed and "temp_file" in locals():
            os.unlink(temp_file.name)


def categorize_backup(backup_path, config):
    """
    Move the backup to daily, weekly, or monthly directory based on timestamp

    Args:
        backup_path: Path to the backup file
        config: Backup configuration dictionary

    Returns:
        New backup path
    """
    now = datetime.now()
    backup_filename = os.path.basename(backup_path)

    # Check if this is a monthly backup (first day of month)
    if now.day == 1:
        backup_type = "monthly"
    # Check if this is a weekly backup (Monday)
    elif now.weekday() == 0:  # Monday is 0
        backup_type = "weekly"
    # Otherwise it's a daily backup
    else:
        backup_type = "daily"

    # Move to appropriate directory
    target_dir = os.path.join(config["backup_dir"], backup_type)
    target_path = os.path.join(target_dir, backup_filename)

    # Also move metadata file if it exists
    metadata_file = f"{backup_path}.meta.json"
    metadata_target = f"{target_path}.meta.json"

    # Move the files
    shutil.move(backup_path, target_path)
    if os.path.exists(metadata_file):
        shutil.move(metadata_file, metadata_target)

    logger.info(f"Backup categorized as '{backup_type}' and moved to {target_path}")
    return target_path


def upload_to_cloud(backup_path, config):
    """
    Upload backup to configured cloud storage

    Args:
        backup_path: Path to the backup file
        config: Backup configuration dictionary

    Returns:
        Dictionary of upload results by storage type
    """
    results = {}
    backup_filename = os.path.basename(backup_path)
    metadata_file = f"{backup_path}.meta.json"

    # Upload to AWS S3 if configured
    if config["storage"].get("s3", False):
        try:
            logger.info(f"Uploading backup to S3: {backup_filename}")
            s3_client = boto3.client(
                "s3", region_name=config["storage"].get("s3_region", "us-east-1")
            )

            bucket = config["storage"].get("s3_bucket", "queueme-backups")
            prefix = config["storage"].get("s3_prefix", "db-backups/")

            # Upload backup file
            s3_key = f"{prefix}{backup_filename}"
            s3_client.upload_file(backup_path, bucket, s3_key)

            # Upload metadata if it exists
            if os.path.exists(metadata_file):
                s3_client.upload_file(
                    metadata_file, bucket, f"{prefix}{os.path.basename(metadata_file)}"
                )

            results["s3"] = {"success": True, "bucket": bucket, "key": s3_key}
            logger.info(f"S3 upload complete: s3://{bucket}/{s3_key}")

        except Exception as e:
            error_msg = f"S3 upload error: {str(e)}"
            logger.error(error_msg)
            results["s3"] = {"success": False, "error": error_msg}

    # Upload to Google Cloud Storage if configured
    if config["storage"].get("gcs", False):
        try:
            logger.info("Uploading backup to GCS: {}".format(backup_filename))
            gcs_client = storage.Client()

            bucket_name = config["storage"].get("gcs_bucket", "queueme-backups")
            prefix = config["storage"].get("gcs_prefix", "db-backups/")

            bucket = gcs_client.bucket(bucket_name)

            # Upload backup file
            gcs_path = f"{prefix}{backup_filename}"
            blob = bucket.blob(gcs_path)
            blob.upload_from_filename(backup_path)

            # Upload metadata if it exists
            if os.path.exists(metadata_file):
                meta_blob = bucket.blob(f"{prefix}{os.path.basename(metadata_file)}")
                meta_blob.upload_from_filename(metadata_file)

            results["gcs"] = {"success": True, "bucket": bucket_name, "path": gcs_path}
            logger.info(f"GCS upload complete: gs://{bucket_name}/{gcs_path}")

        except Exception as e:
            error_msg = f"GCS upload error: {str(e)}"
            logger.error(error_msg)
            results["gcs"] = {"success": False, "error": error_msg}

    return results


def cleanup_old_backups(config):
    """
    Delete old backups based on retention policy

    Args:
        config: Backup configuration dictionary

    Returns:
        Number of files cleaned up
    """
    logger.info("Running backup cleanup based on retention policy")
    cleanup_count = 0

    # Clean up daily backups
    daily_retention = config["retention"].get("daily", 7)
    daily_cutoff = datetime.now() - timedelta(days=daily_retention)
    cleanup_count += cleanup_directory(
        os.path.join(config["backup_dir"], "daily"), daily_cutoff
    )

    # Clean up weekly backups
    weekly_retention = config["retention"].get("weekly", 4)
    weekly_cutoff = datetime.now() - timedelta(weeks=weekly_retention)
    cleanup_count += cleanup_directory(
        os.path.join(config["backup_dir"], "weekly"), weekly_cutoff
    )

    # Clean up monthly backups
    monthly_retention = config["retention"].get("monthly", 12)
    monthly_cutoff = datetime.now() - timedelta(days=30 * monthly_retention)
    cleanup_count += cleanup_directory(
        os.path.join(config["backup_dir"], "monthly"), monthly_cutoff
    )

    logger.info(f"Backup cleanup completed: {cleanup_count} files removed")
    return cleanup_count


def cleanup_directory(directory, cutoff_date):
    """
    Delete files in directory older than cutoff date

    Args:
        directory: Directory to clean
        cutoff_date: Delete files older than this date

    Returns:
        Number of files deleted
    """
    if not os.path.exists(directory):
        return 0

    cleanup_count = 0
    for filename in os.listdir(directory):
        filepath = os.path.join(directory, filename)

        # Skip directories
        if not os.path.isfile(filepath):
            continue

        # Skip non-backup files
        if not (
            filename.startswith("queueme_backup_")
            and (filename.endswith(".sql") or filename.endswith(".sql.gz"))
        ):
            continue

        # Check file modification time
        file_mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
        if file_mtime < cutoff_date:
            try:
                # Also delete metadata file if it exists
                metadata_path = f"{filepath}.meta.json"
                if os.path.exists(metadata_path):
                    os.remove(metadata_path)

                # Delete the backup file
                os.remove(filepath)
                cleanup_count += 1
                logger.info(f"Deleted old backup: {filepath}")

            except Exception as e:
                logger.error(f"Failed to delete old backup {filepath}: {str(e)}")

    return cleanup_count


def calculate_file_hash(file_path):
    """Calculate SHA-256 hash of file"""
    sha256_hash = hashlib.sha256()

    with open(file_path, "rb") as f:
        # Read and update hash in chunks for memory efficiency
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

    return sha256_hash.hexdigest()


def send_notification(success, backup_details, config, error=None):
    """
    Send notification about backup status

    Args:
        success: Whether backup was successful
        backup_details: Details about the backup
        config: Backup configuration
        error: Error message if backup failed
    """
    if not config.get("notify", True):
        return

    # Try to import Django for notification sending
    try:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "queueme.settings")
        import django

        django.setup()

        from apps.notificationsapp.services.notification_service import (
            NotificationService,
        )

        # Construct message
        if success:
            title = "Database Backup Successful"
            message = f"Backup completed successfully at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            message += f"Backup file: {os.path.basename(backup_details['path'])}\n"
            message += f"Size: {backup_details['size'] / (1024*1024):.2f} MB\n"

            # Add cloud storage info
            if "cloud_uploads" in backup_details:
                message += "\nCloud Storage:\n"
                for storage_type, result in backup_details["cloud_uploads"].items():
                    if result.get("success", False):
                        if storage_type == "s3":
                            message += (
                                f"AWS S3: s3://{result['bucket']}/{result['key']}\n"
                            )
                        elif storage_type == "gcs":
                            message += f"Google Cloud Storage: gs://{result['bucket']}/{result['path']}\n"
        else:
            title = "Database Backup Failed"
            message = (
                f"Backup failed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            )
            message += f"Error: {error}\n"

        # Send admin notification
        NotificationService.send_notification(
            recipient_id=config.get(
                "notify_admin_id", "00000000-0000-0000-0000-000000000001"
            ),
            notification_type="database_backup",
            title=title,
            message=message,
            channels=["email", "in_app"],
            priority="high" if not success else "normal",
        )

    except Exception as e:
        logger.error(f"Failed to send notification: {str(e)}")


def run_backup():
    """Main backup function"""
    parser = argparse.ArgumentParser(description="QueueMe Database Backup Script")
    parser.add_argument("-c", "--config", help="Path to config file")
    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config)
    logger.info("Starting QueueMe database backup")

    # Get database configuration
    db_config = get_database_config()

    # Create backup
    success, backup_path, error = create_backup(
        db_config, config["backup_dir"], compress=config["compression"]
    )

    if not success:
        logger.error(f"Backup failed: {error}")
        send_notification(False, None, config, error)
        return False

    # Verify backup
    verify_success, verify_error = verify_backup(backup_path)
    if not verify_success:
        logger.error(f"Backup verification failed: {verify_error}")
        send_notification(False, None, config, verify_error)
        return False

    # Categorize backup (daily/weekly/monthly)
    backup_path = categorize_backup(backup_path, config)

    # Get backup file details
    backup_size = os.path.getsize(backup_path)
    logger.info(f"Backup file size: {backup_size / (1024*1024):.2f} MB")

    backup_details = {
        "path": backup_path,
        "size": backup_size,
        "timestamp": datetime.now().isoformat(),
    }

    # Upload to cloud storage if configured
    if config["storage"].get("s3", False) or config["storage"].get("gcs", False):
        cloud_results = upload_to_cloud(backup_path, config)
        backup_details["cloud_uploads"] = cloud_results

    # Clean up old backups
    cleanup_old_backups(config)

    # Send notification
    send_notification(True, backup_details, config)

    logger.info("Database backup completed successfully")
    return True


if __name__ == "__main__":
    run_backup()
