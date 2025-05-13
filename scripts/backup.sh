#!/bin/bash
# =============================================================================
# Queue Me Backup Script
# Advanced database, media, and configuration backup with rotation and integrity
# =============================================================================

set -e

# Configuration
BACKUP_DIR="/var/backups/queueme"
DB_BACKUP_DIR="$BACKUP_DIR/database"
MEDIA_BACKUP_DIR="$BACKUP_DIR/media"
CONFIG_BACKUP_DIR="$BACKUP_DIR/config"
LOG_FILE="$BACKUP_DIR/backup.log"
RETENTION_DAYS=14

# Environment-specific settings (load from .env if exists)
ENV_FILE="../.env"
if [ -f "$ENV_FILE" ]; then
    source "$ENV_FILE"
fi

# Default database settings if not in .env
DB_NAME=${POSTGRES_DB:-queueme}
DB_USER=${POSTGRES_USER:-queueme}
DB_PASSWORD=${POSTGRES_PASSWORD:-queueme}
DB_HOST=${POSTGRES_HOST:-localhost}
DB_PORT=${POSTGRES_PORT:-5432}

# AWS S3 settings
AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID:-""}
AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY:-""}
AWS_BUCKET=${AWS_STORAGE_BUCKET_NAME:-""}
AWS_REGION=${AWS_S3_REGION_NAME:-"me-south-1"}

# Create backup directories if they don't exist
mkdir -p "$DB_BACKUP_DIR" "$MEDIA_BACKUP_DIR" "$CONFIG_BACKUP_DIR"

# Timestamp for backup files
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
DATE_ONLY=$(date +"%Y%m%d")

# Function for logging
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Function to check if a command is available
check_command() {
    if ! command -v "$1" &> /dev/null; then
        log "ERROR: $1 command not found. Please install it."
        exit 1
    fi
}

# Check required commands
check_command pg_dump
check_command aws
check_command gzip

# Database backup
backup_database() {
    log "Starting database backup..."
    DB_BACKUP_FILE="$DB_BACKUP_DIR/${DATE_ONLY}_${DB_NAME}.sql.gz"

    # Create backup with retry mechanism
    RETRIES=3
    for i in $(seq 1 $RETRIES); do
        if PGPASSWORD="$DB_PASSWORD" pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -F c | gzip > "$DB_BACKUP_FILE"; then
            log "Database backup completed: $DB_BACKUP_FILE"
            break
        else
            log "Attempt $i failed. Retrying..."
            if [ $i -eq $RETRIES ]; then
                log "ERROR: Database backup failed after $RETRIES attempts"
                return 1
            fi
            sleep 5
        fi
    done

    # Verify backup integrity
    if gzip -t "$DB_BACKUP_FILE"; then
        log "Backup integrity verified"
    else
        log "ERROR: Backup file is corrupted"
        return 1
    fi

    return 0
}

# S3 Media backup
backup_media() {
    if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ] || [ -z "$AWS_BUCKET" ]; then
        log "WARNING: AWS credentials not configured. Skipping media backup."
        return 0
    fi

    log "Starting media backup from S3..."
    MEDIA_BACKUP_FILE="$MEDIA_BACKUP_DIR/${DATE_ONLY}_media_list.txt"

    # List all objects and download metadata to track what's in S3
    aws s3 ls "s3://$AWS_BUCKET/" --recursive > "$MEDIA_BACKUP_FILE"
    if [ $? -ne 0 ]; then
        log "ERROR: Failed to list S3 objects"
        return 1
    fi

    log "Media inventory completed: $MEDIA_BACKUP_FILE"

    # Optional: Sync a local copy of media (commented out to avoid large downloads)
    # log "Syncing media files locally (this may take time)..."
    # aws s3 sync "s3://$AWS_BUCKET/" "$MEDIA_BACKUP_DIR/files/"

    return 0
}

# Configuration backup
backup_config() {
    log "Starting configuration backup..."
    CONFIG_BACKUP_FILE="$CONFIG_BACKUP_DIR/${DATE_ONLY}_config.tar.gz"

    # Create tar of all configuration files
    tar -czf "$CONFIG_BACKUP_FILE" \
        -C ../ \
        .env \
        queueme/settings/*.py \
        config/nginx/*.conf \
        config/supervisor/*.conf \
        config/redis/*.conf

    if [ $? -ne 0 ]; then
        log "ERROR: Configuration backup failed"
        return 1
    fi

    log "Configuration backup completed: $CONFIG_BACKUP_FILE"
    return 0
}

# Clean up old backups
cleanup_old_backups() {
    log "Cleaning up backups older than $RETENTION_DAYS days..."

    find "$DB_BACKUP_DIR" -type f -name "*.sql.gz" -mtime +$RETENTION_DAYS -delete
    find "$MEDIA_BACKUP_DIR" -type f -name "*.txt" -mtime +$RETENTION_DAYS -delete
    find "$CONFIG_BACKUP_DIR" -type f -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete

    log "Cleanup completed"
}

# Upload to offsite (optional)
upload_offsite() {
    if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ] || [ -z "$AWS_BUCKET" ]; then
        log "WARNING: AWS credentials not configured. Skipping offsite upload."
        return 0
    fi

    OFFSITE_DIR="backups/$DATE_ONLY"
    log "Uploading backups to offsite storage (S3)..."

    # Upload database backup
    aws s3 cp "$DB_BACKUP_FILE" "s3://$AWS_BUCKET/$OFFSITE_DIR/"

    # Upload config backup
    aws s3 cp "$CONFIG_BACKUP_FILE" "s3://$AWS_BUCKET/$OFFSITE_DIR/"

    log "Offsite upload completed"
}

# Main execution
log "===== Starting Queue Me Backup Process ====="

# Run each backup component
backup_database && backup_media && backup_config && cleanup_old_backups && upload_offsite

RESULT=$?
if [ $RESULT -eq 0 ]; then
    log "===== Backup Process Completed Successfully ====="
else
    log "===== Backup Process Failed with Errors ====="
fi

exit $RESULT
