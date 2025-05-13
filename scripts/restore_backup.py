#!/usr/bin/env python
"""
Database Restore Script for QueueMe

This script restores a database backup with the following features:
1. Verification of backup file integrity
2. Support for compressed backups
3. Optional download from cloud storage (AWS S3, Google Cloud Storage)
4. Notification on restore completion or failure
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
from datetime import datetime

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
        logging.FileHandler(os.path.join(PROJECT_DIR, "logs", "database_restore.log")),
    ],
)
logger = logging.getLogger("database_restore")


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


def verify_backup_file(backup_path):
    """
    Verify the integrity of the backup file

    Args:
        backup_path: Path to the backup file

    Returns:
        Tuple of (success, error_message)
    """
    # Check if file exists and is readable
    if not os.path.exists(backup_path):
        return False, f"Backup file not found: {backup_path}"

    # Check if file is empty
    if os.path.getsize(backup_path) == 0:
        return False, f"Backup file is empty: {backup_path}"

    # Check if metadata file exists
    metadata_path = f"{backup_path}.meta.json"
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, "r") as f:
                metadata = json.load(f)

            # Verify file hash if available in metadata
            if "sha256" in metadata:
                actual_hash = calculate_file_hash(backup_path)
                if actual_hash != metadata["sha256"]:
                    return (
                        False,
                        f"Backup file hash mismatch. Expected: {metadata['sha256']}, Got: {actual_hash}",
                    )
                logger.info("Backup file hash verified successfully")
        except Exception as e:
            logger.warning(f"Error reading backup metadata: {str(e)}")

    # Try to check backup validity by listing its contents
    is_compressed = backup_path.endswith(".gz")

    if is_compressed:
        try:
            # Create a temporary file for the decompressed content
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            with gzip.open(backup_path, "rb") as f_in:
                with open(temp_file.name, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)

            verify_path = temp_file.name
        except Exception as e:
            return False, f"Error decompressing backup: {str(e)}"
    else:
        verify_path = backup_path

    try:
        # Try to list contents of the backup
        cmd = ["pg_restore", "-l", verify_path]
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Check if we got content listing output
        if result.stdout:
            logger.info("Backup file verified successfully")
            return True, None
        else:
            return False, "Unable to list backup contents"

    except subprocess.CalledProcessError as e:
        return False, f"Backup verification failed: {e.stderr.decode()}"
    except Exception as e:
        return False, f"Error verifying backup: {str(e)}"
    finally:
        # Clean up temp file if used
        if is_compressed and "temp_file" in locals():
            os.unlink(temp_file.name)


def calculate_file_hash(file_path):
    """Calculate SHA-256 hash of file"""
    sha256_hash = hashlib.sha256()

    with open(file_path, "rb") as f:
        # Read and update hash in chunks for memory efficiency
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

    return sha256_hash.hexdigest()


def download_from_s3(bucket, key, output_path):
    """
    Download backup file from AWS S3

    Args:
        bucket: S3 bucket name
        key: S3 object key
        output_path: Path to save the downloaded file

    Returns:
        Tuple of (success, error_message)
    """
    try:
        logger.info(f"Downloading backup from S3: s3://{bucket}/{key}")
        s3_client = boto3.client("s3")
        s3_client.download_file(bucket, key, output_path)

        # Also download metadata if available
        try:
            metadata_key = f"{key}.meta.json"
            metadata_path = f"{output_path}.meta.json"
            s3_client.download_file(bucket, metadata_key, metadata_path)
            logger.info("Downloaded backup metadata")
        except Exception as e:
            logger.warning(f"Could not download metadata file: {str(e)}")

        logger.info("Download from S3 completed successfully")
        return True, None
    except Exception as e:
        return False, f"Error downloading from S3: {str(e)}"


def download_from_gcs(bucket, path, output_path):
    """
    Download backup file from Google Cloud Storage

    Args:
        bucket: GCS bucket name
        path: GCS object path
        output_path: Path to save the downloaded file

    Returns:
        Tuple of (success, error_message)
    """
    try:
        logger.info(f"Downloading backup from GCS: gs://{bucket}/{path}")
        gcs_client = storage.Client()
        bucket = gcs_client.bucket(bucket)

        # Download backup file
        blob = bucket.blob(path)
        blob.download_to_filename(output_path)

        # Also download metadata if available
        try:
            metadata_path = f"{path}.meta.json"
            metadata_output = f"{output_path}.meta.json"
            metadata_blob = bucket.blob(metadata_path)
            metadata_blob.download_to_filename(metadata_output)
            logger.info("Downloaded backup metadata")
        except Exception as e:
            logger.warning(f"Could not download metadata file: {str(e)}")

        logger.info("Download from GCS completed successfully")
        return True, None
    except Exception as e:
        return False, f"Error downloading from GCS: {str(e)}"


def restore_backup(backup_path, db_config, options=None):
    """
    Restore a database backup

    Args:
        backup_path: Path to the backup file
        db_config: Database configuration dictionary
        options: Additional restore options

    Returns:
        Tuple of (success, error_message)
    """
    # Verify backup file first
    verify_success, verify_error = verify_backup_file(backup_path)
    if not verify_success:
        return False, f"Backup verification failed: {verify_error}"

    # Handle compressed backups
    is_compressed = backup_path.endswith(".gz")

    if is_compressed:
        try:
            logger.info("Decompressing backup file")
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            with gzip.open(backup_path, "rb") as f_in:
                with open(temp_file.name, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)

            restore_path = temp_file.name
            logger.info("Backup decompressed successfully")
        except Exception as e:
            return False, f"Error decompressing backup: {str(e)}"
    else:
        restore_path = backup_path

    try:
        logger.info(f"Starting database restore to {db_config['name']}")

        # Setup environment variables for pg_restore
        env = os.environ.copy()
        if db_config["password"]:
            env["PGPASSWORD"] = db_config["password"]

        # Prepare restore options
        restore_options = options or {}
        clean = restore_options.get("clean", True)
        create = restore_options.get("create", True)
        no_owner = restore_options.get("no_owner", True)

        # Build pg_restore command
        cmd = [
            "pg_restore",
            "-h",
            db_config["host"],
            "-p",
            db_config["port"],
            "-U",
            db_config["user"],
            "-d",
            db_config["name"],
            "-v",  # Verbose output
        ]

        if clean:
            cmd.append("--clean")
        if create:
            cmd.append("--create")
        if no_owner:
            cmd.append("--no-owner")

        cmd.append(restore_path)

        # Execute restore command
        logger.info(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(
            cmd, env=env, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        logger.info("Database restore completed successfully")
        return True, None

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode()
        logger.error(f"pg_restore error: {error_msg}")
        return False, f"pg_restore error: {error_msg}"
    except Exception as e:
        logger.error(f"Restore error: {str(e)}")
        return False, f"Restore error: {str(e)}"
    finally:
        # Clean up temp file if used
        if is_compressed and "temp_file" in locals():
            os.unlink(temp_file.name)


def send_notification(success, details=None, error=None):
    """
    Send notification about restore status

    Args:
        success: Whether restore was successful
        details: Details about the restore operation
        error: Error message if restore failed
    """
    try:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "queueme.settings")
        import django

        django.setup()

        from apps.notificationsapp.services.notification_service import NotificationService

        # Construct message
        if success:
            title = "Database Restore Successful"
            message = f"Database restore completed successfully at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            if details and "backup_path" in details:
                message += f"Backup file: {os.path.basename(details['backup_path'])}\n"
        else:
            title = "Database Restore Failed"
            message = f"Database restore failed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            message += f"Error: {error}\n"

        # Send admin notification
        NotificationService.send_notification(
            recipient_id="00000000-0000-0000-0000-000000000001",  # Admin user ID
            notification_type="database_restore",
            title=title,
            message=message,
            channels=["email", "in_app"],
            priority="high" if not success else "normal",
        )

        logger.info("Sent notification about restore status")

    except Exception as e:
        logger.error(f"Failed to send notification: {str(e)}")


def main():
    parser = argparse.ArgumentParser(description="QueueMe Database Restore Script")
    parser.add_argument(
        "backup_path",
        help="Path to backup file or cloud storage URL (s3://bucket/key or gs://bucket/path)",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean (drop) database objects before recreating them",
    )
    parser.add_argument(
        "--create",
        action="store_true",
        help="Create the database before restoring into it",
    )
    parser.add_argument(
        "--no-owner",
        action="store_true",
        help="Don't output commands to set ownership of objects",
    )
    parser.add_argument(
        "--no-notify", action="store_true", help="Don't send notification after restore"
    )
    args = parser.parse_args()

    # Process backup path/URL
    backup_path = args.backup_path

    # Convert cloud storage URLs to local files if needed
    if backup_path.startswith("s3://"):
        # Extract bucket and key from S3 URL
        path_parts = backup_path[5:].split("/", 1)
        if len(path_parts) != 2:
            logger.error("Invalid S3 URL format. Expected: s3://bucket/key")
            return 1

        bucket, key = path_parts

        # Create a temporary file for the download
        local_backup = tempfile.NamedTemporaryFile(delete=False, suffix=".sql")
        local_backup.close()

        # Download from S3
        download_success, download_error = download_from_s3(bucket, key, local_backup.name)
        if not download_success:
            logger.error(f"Download failed: {download_error}")
            return 1

        backup_path = local_backup.name

    elif backup_path.startswith("gs://"):
        # Extract bucket and path from GCS URL
        path_parts = backup_path[5:].split("/", 1)
        if len(path_parts) != 2:
            logger.error("Invalid GCS URL format. Expected: gs://bucket/path")
            return 1

        bucket, path = path_parts

        # Create a temporary file for the download
        local_backup = tempfile.NamedTemporaryFile(delete=False, suffix=".sql")
        local_backup.close()

        # Download from GCS
        download_success, download_error = download_from_gcs(bucket, path, local_backup.name)
        if not download_success:
            logger.error(f"Download failed: {download_error}")
            return 1

        backup_path = local_backup.name

    # Get database configuration
    db_config = get_database_config()

    # Prepare restore options
    restore_options = {
        "clean": args.clean,
        "create": args.create,
        "no_owner": args.no_owner,
    }

    # Execute restore
    restore_success, restore_error = restore_backup(backup_path, db_config, restore_options)

    # Send notification
    if not args.no_notify:
        details = {"backup_path": backup_path} if restore_success else None
        send_notification(restore_success, details, restore_error)

    # Clean up temporary files
    if backup_path.startswith("/tmp/") and "local_backup" in locals():
        try:
            os.unlink(backup_path)
            metadata_path = f"{backup_path}.meta.json"
            if os.path.exists(metadata_path):
                os.unlink(metadata_path)
        except Exception as e:
            logger.warning(f"Error cleaning up temporary files: {str(e)}")

    if restore_success:
        logger.info("Database restore completed successfully")
        return 0
    else:
        logger.error(f"Database restore failed: {restore_error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
