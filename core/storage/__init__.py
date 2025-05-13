"""
Storage module for QueueMe application.
"""

from .s3 import MediaStorage, StaticStorage

__all__ = ["MediaStorage", "StaticStorage"]
