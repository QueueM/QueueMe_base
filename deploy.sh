# File: /home/arise/queueme/deploy.sh

#!/bin/bash
# QueueMe deployment script with automatic documentation update

set -e  # Exit on error

# Display a timestamp
echo "Starting deployment at $(date)"

# Go to the project directory
cd /home/arise/queueme

# Pull latest changes
git pull

# Update dependencies
source venv/bin/activate
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Update documentation
python update_docs.py

# Restart services
sudo systemctl restart queueme.service
sudo systemctl restart queueme-daphne.service
sudo systemctl restart queueme-celery.service
sudo systemctl restart queueme-celery-beat.service
sudo systemctl restart nginx

echo "Deployment completed at $(date)"
