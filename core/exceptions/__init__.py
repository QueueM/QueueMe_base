"""
Queue Me – centralised custom exceptions.

Import these from `core.exceptions` across the project instead of redefining
ad-hoc `Exception` subclasses in each app.
"""

from __future__ import annotations


class QueueMeBaseException(Exception):
    """Base class for all custom exceptions in the Queue Me backend.

    Catch this (or a concrete subclass) in views / tasks when you want to
    convert internal errors into HTTP responses without leaking implementation
    details.
    """


class MediaProcessingException(QueueMeBaseException):
    """Raised when an uploaded image / video fails processing steps.

    Typical scenarios:
    * FFMpeg can’t transcode the reel video.
    * PIL can’t generate a thumbnail.
    * File format or codec not supported.

    `core.storage.media_processor` raises this so callers can decide whether to
    mark the upload as “failed”, retry, or notify the uploader.
    """


__all__ = [
    "QueueMeBaseException",
    "MediaProcessingException",
]
