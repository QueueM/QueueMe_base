import os

import magic
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_video_file_extension(value):
    """
    Validate that uploaded file is a valid video format.
    """
    ext = os.path.splitext(value.name)[1].lower()
    valid_extensions = [".mp4", ".mov", ".avi", ".wmv", ".flv", ".mkv"]

    if ext not in valid_extensions:
        raise ValidationError(
            _("Unsupported file extension. Allowed extensions are: %(extensions)s."),
            params={"extensions": ", ".join(valid_extensions)},
        )


def validate_video_file_mime_type(value):
    """
    Validate that uploaded file has a valid video MIME type.
    """
    # Read the first 2048 bytes to determine file type
    file_mime = magic.from_buffer(value.read(2048), mime=True)
    # Reset file pointer
    value.seek(0)

    valid_mime_types = [
        "video/mp4",
        "video/quicktime",
        "video/x-msvideo",
        "video/x-ms-wmv",
        "video/x-flv",
        "video/x-matroska",
    ]

    if file_mime not in valid_mime_types:
        raise ValidationError(
            _("Unsupported file type. Uploaded file is not a valid video format.")
        )


def validate_video_file_size(value):
    """
    Validate that uploaded video file size is within acceptable limits.
    """
    # Default size limit: 50MB
    size_limit = getattr(settings, "MAX_REEL_VIDEO_SIZE", 50 * 1024 * 1024)

    if value.size > size_limit:
        raise ValidationError(
            _("Video file too large. Size should not exceed %(limit)s MB."),
            params={"limit": size_limit / (1024 * 1024)},
        )


def validate_video(value):
    """
    Composite validator for video files.
    """
    validate_video_file_extension(value)
    validate_video_file_mime_type(value)
    validate_video_file_size(value)
