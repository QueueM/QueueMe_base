#!/bin/bash
# =============================================================================
# Queue Me Deployment Script
# Sophisticated blue-green deployment with zero downtime
# =============================================================================

set -e

# Configuration
PROJECT_DIR="/opt/queueme"
GIT_REPO="https://github.com/QueueM/queueme_backend.git"
BRANCH="main"
ENV_FILE="$PROJECT_DIR/.env"
BACKUP_SCRIPT="$PROJECT_DIR/scripts/backup.sh"
LOG_FILE="$PROJECT_DIR/deploy.log"

# Blue-green deployment settings
BLUE_PORT=8010
GREEN_PORT=8011
ACTIVE_COLOR_FILE="$PROJECT_DIR/.active_color"
CURRENT_COLOR=$(cat "$ACTIVE_COLOR_FILE" 2>/dev/null || echo "blue")
NGINX_CONF="/etc/nginx/sites-available/queueme.conf"

# Health check settings
HEALTH_CHECK_URL="http://localhost"
HEALTH_CHECK_TIMEOUT=60
HEALTH_CHECK_INTERVAL=2

# Function for logging
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Ensure we're in the project directory
cd "$PROJECT_DIR" || { log "ERROR: Project directory not found"; exit 1; }

# Determine next color
if [ "$CURRENT_COLOR" == "blue" ]; then
    NEXT_COLOR="green"
    NEXT_PORT=$GREEN_PORT
else
    NEXT_COLOR="blue"
    NEXT_PORT=$BLUE_PORT
fi

log "Starting deployment (Current: $CURRENT_COLOR, Next: $NEXT_COLOR)"

# Step 1: Run backup before deployment
log "Running backup..."
$BACKUP_SCRIPT || { log "WARNING: Backup failed, continuing deployment"; }

# Step 2: Prepare next environment
NEXT_DIR="$PROJECT_DIR/$NEXT_COLOR"
log "Preparing $NEXT_COLOR environment..."

# Create or clear directory
if [ -d "$NEXT_DIR" ]; then
    # Preserve virtualenv
    mv "$NEXT_DIR/venv" "$NEXT_DIR/venv_save" 2>/dev/null || true
    rm -rf "$NEXT_DIR"/*
    mkdir -p "$NEXT_DIR"
    [ -d "$NEXT_DIR/venv_save" ] && mv "$NEXT_DIR/venv_save" "$NEXT_DIR/venv"
else
    mkdir -p "$NEXT_DIR"
fi

# Step 3: Clone the latest code
log "Cloning repository..."
git clone -b "$BRANCH" --single-branch "$GIT_REPO" "$NEXT_DIR/app"
cd "$NEXT_DIR/app"

# Step 4: Set up virtual environment
if [ ! -d "$NEXT_DIR/venv" ]; then
    log "Creating virtual environment..."
    python3 -m venv "$NEXT_DIR/venv"
fi

source "$NEXT_DIR/venv/bin/activate"
pip install --upgrade pip
pip install -r requirements.txt

# Step 5: Copy environment file
log "Copying environment file..."
cp "$ENV_FILE" "$NEXT_DIR/app/.env"

# Step 6: Run database migrations
log "Running database migrations..."
python manage.py migrate --noinput

# Step 7: Collect static files
log "Collecting static files..."
python manage.py collectstatic --noinput

# Step 8: Start the new application
log "Starting $NEXT_COLOR application on port $NEXT_PORT..."
sed "s/PORT=8000/PORT=$NEXT_PORT/" "$ENV_FILE" > "$NEXT_DIR/app/.env"

# Stop any existing process on this port
pkill -f "gunicorn.*:$NEXT_PORT" || true
sleep 2

# Start with Gunicorn
cd "$NEXT_DIR/app"
gunicorn queueme.wsgi:application \
    --bind 0.0.0.0:$NEXT_PORT \
    --workers 4 \
    --timeout 120 \
    --access-logfile "$NEXT_DIR/access.log" \
    --error-logfile "$NEXT_DIR/error.log" \
    --daemon

# Step 9: Run health checks
log "Running health checks on new deployment..."
HEALTH_CHECK_URL="$HEALTH_CHECK_URL:$NEXT_PORT/api/health/"

successful_checks=0
required_successful_checks=3

for ((i=1; i<=$HEALTH_CHECK_TIMEOUT; i+=$HEALTH_CHECK_INTERVAL)); do
    response=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_CHECK_URL" || echo "000")

    if [ "$response" == "200" ]; then
        successful_checks=$((successful_checks + 1))
        log "Health check passed ($successful_checks/$required_successful_checks)"

        if [ $successful_checks -ge $required_successful_checks ]; then
            break
        fi
    else
        successful_checks=0
        log "Health check failed (HTTP $response), retrying in $HEALTH_CHECK_INTERVAL seconds..."
    fi

    sleep $HEALTH_CHECK_INTERVAL

    if [ $i -ge $HEALTH_CHECK_TIMEOUT ]; then
        log "ERROR: Health checks failed after timeout period"
        log "Rolling back to $CURRENT_COLOR deployment"
        pkill -f "gunicorn.*:$NEXT_PORT" || true
        exit 1
    fi
done

# Step 10: Update Nginx configuration
log "Updating Nginx configuration..."
sed -i "s/proxy_pass http:\/\/localhost:[0-9]\+/proxy_pass http:\/\/localhost:$NEXT_PORT/" "$NGINX_CONF"
nginx -t && systemctl reload nginx

# Step 11: Update active color marker
echo "$NEXT_COLOR" > "$ACTIVE_COLOR_FILE"

# Step 12: Gracefully shutdown old deployment
log "Gracefully shutting down $CURRENT_COLOR deployment..."
if [ "$CURRENT_COLOR" == "blue" ]; then
    OLD_PORT=$BLUE_PORT
else
    OLD_PORT=$GREEN_PORT
fi

# Wait for active connections to finish (up to 30 seconds)
pkill -TERM -f "gunicorn.*:$OLD_PORT" || true
sleep 30
pkill -KILL -f "gunicorn.*:$OLD_PORT" || true

log "Deployment completed successfully: $NEXT_COLOR environment is now active"
log "===== Deployment Completed ====="

# Optional: Trigger any post-deployment tasks
log "Running post-deployment tasks..."
source "$NEXT_DIR/venv/bin/activate"
cd "$NEXT_DIR/app"
python manage.py clear_cache
python manage.py update_search_index

log "Post-deployment tasks completed"
exit 0
