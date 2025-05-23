"""
API Documentation package initialization

This module ensures that all necessary patches and configurations
are applied when Django loads the documentation package.
"""

import logging

logger = logging.getLogger(__name__)

# Import the patch to ensure it's applied when the package is loaded
try:
    from . import yasg_patch
    logger.info("Successfully loaded yasg_patch module")
except ImportError as e:
    logger.error(f"Failed to import yasg_patch: {e}")

# Import utilities to ensure patches are applied
try:
    from . import utils
    logger.info("Successfully loaded documentation utils")
except ImportError as e:
    logger.error(f"Failed to import documentation utils: {e}")

# Import other documentation modules
try:
    from . import parameters
    from . import api_doc_decorators
    logger.info("Successfully loaded all documentation modules")
except ImportError as e:
    logger.warning(f"Failed to import some documentation modules: {e}")

__all__ = [
    'yasg_patch',
    'utils',
    'parameters',
    'api_doc_decorators',
]

# Log that the documentation package has been initialized
logger.info("API documentation package initialized successfully")
