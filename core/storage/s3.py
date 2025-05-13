"""
Storage classes for AWS S3 integration.
"""

from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage


class StaticStorage(S3Boto3Storage):
    """
    Storage class for static files on S3.
    """

    location = getattr(settings, "AWS_LOCATION", "static")
    default_acl = getattr(settings, "AWS_DEFAULT_ACL", "public-read")
    file_overwrite = True
    custom_domain = getattr(settings, "AWS_S3_CUSTOM_DOMAIN", None)
    querystring_auth = False  # Don't add querystring auth to URLs

    # Custom cache headers for static files
    object_parameters = {
        "CacheControl": "max-age=86400,public",  # 1 day cache
    }


class MediaStorage(S3Boto3Storage):
    """
    Storage class for media files on S3.
    """

    location = getattr(settings, "MEDIA_LOCATION", "media")
    default_acl = getattr(settings, "AWS_DEFAULT_ACL", "public-read")
    file_overwrite = False  # Don't overwrite files with same name
    custom_domain = getattr(settings, "AWS_S3_CUSTOM_DOMAIN", None)
    querystring_auth = True  # Include auth for private files if needed

    # Custom cache headers for media files
    object_parameters = {
        "CacheControl": "max-age=3600,public",  # 1 hour cache
    }
