#!/usr/bin/env python
"""
Script to automatically update API documentation
This script is designed to be run by a cron job
"""

import os
import sys
import django
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    filename='/home/arise/queueme/logs/doc_updates.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'queueme.settings.production')
sys.path.append('/home/arise/queueme')

try:
    django.setup()
    logging.info("Starting API documentation update process")
    
    # Import after Django setup
    from django.core.management import call_command
    from enhanced_docs_generator import EnhancedDocsGenerator
    
    # Run the management command to generate static documentation
    logging.info("Generating static API documentation")
    call_command('generate_api_docs')
    
    # Generate enhanced documentation
    logging.info("Generating enhanced API documentation")
    generator = EnhancedDocsGenerator()
    generator.generate_comprehensive_docs()
    
    logging.info(f"API documentation update completed successfully at {datetime.now()}")
    
except Exception as e:
    logging.error(f"Error updating API documentation: {str(e)}")
    sys.exit(1)
