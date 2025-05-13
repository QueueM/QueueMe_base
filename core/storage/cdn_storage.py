"""
CDN Storage Backend

A flexible CDN storage backend for Django that supports multiple CDN providers
with optimized file delivery, cache control, and URL generation.
"""

import base64
import hashlib
import hmac
import os
import time
from urllib.parse import urlencode, urljoin, urlparse, urlunparse

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import FileSystemStorage, Storage
from django.utils.deconstruct import deconstructible
from django.utils.encoding import filepath_to_uri
from django.utils.functional import cached_property
from storages.backends.s3boto3 import S3Boto3Storage

# Default configuration with fallbacks to settings
DEFAULT_CDN_URL = getattr(settings, "CDN_URL", None)
DEFAULT_CDN_PROVIDER = getattr(settings, "CDN_PROVIDER", "cloudfront")
DEFAULT_MEDIA_URL = getattr(settings, "MEDIA_URL", "/media/")
DEFAULT_STATIC_URL = getattr(settings, "STATIC_URL", "/static/")
DEFAULT_CACHE_CONTROL = getattr(settings, "CDN_CACHE_CONTROL", "public, max-age=86400")
DEFAULT_ALLOWED_EXTENSIONS = getattr(
    settings,
    "CDN_ALLOWED_EXTENSIONS",
    [".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".webm", ".mp3", ".pdf", ".svg"],
)
DEFAULT_MAX_AGE = getattr(settings, "CDN_MAX_AGE_SECONDS", 24 * 60 * 60)  # 24 hours
DEFAULT_AWS_STORAGE_BUCKET_NAME = getattr(settings, "AWS_STORAGE_BUCKET_NAME", None)
DEFAULT_S3_CUSTOM_DOMAIN = getattr(settings, "AWS_S3_CUSTOM_DOMAIN", None)
DEFAULT_S3_REGION_NAME = getattr(settings, "AWS_S3_REGION_NAME", None)

# Get provider-specific keys if available
CF_KEY_ID = getattr(settings, "CLOUDFRONT_KEY_ID", None)
CF_PRIVATE_KEY = getattr(settings, "CLOUDFRONT_PRIVATE_KEY", None)
CF_DISTRIBUTION_ID = getattr(settings, "CLOUDFRONT_DISTRIBUTION_ID", None)
AKAMAI_TOKEN_KEY = getattr(settings, "AKAMAI_TOKEN_KEY", None)
AKAMAI_TOKEN_ALGO = getattr(settings, "AKAMAI_TOKEN_ALGO", "sha256")


@deconstructible
class CDNStorage(Storage):
    """
    Base CDN storage class that provides common functionality
    for all CDN providers.
    """

    def __init__(
        self,
        provider=None,
        cdn_url=None,
        static_cdn_url=None,
        media_cdn_url=None,
        location=None,
        base_url=None,
        file_permissions_mode=None,
        directory_permissions_mode=None,
        private_files=False,
        cache_control=None,
        **kwargs,
    ):
        """
        Initialize the CDN storage backend

        Args:
            provider: CDN provider ('cloudfront', 'akamai', 'custom')
            cdn_url: Base CDN URL for both static and media
            static_cdn_url: Specific CDN URL for static files
            media_cdn_url: Specific CDN URL for media files
            location: Base file system location (for local fallback)
            base_url: Base URL (for local fallback)
            file_permissions_mode: Permissions for files (for local fallback)
            directory_permissions_mode: Permissions for directories (for local fallback)
            private_files: Whether files should be private/secured
            cache_control: Cache-Control header value
            **kwargs: Additional provider-specific options
        """
        self.provider = provider or DEFAULT_CDN_PROVIDER
        self.cdn_url = cdn_url or DEFAULT_CDN_URL
        self.media_cdn_url = media_cdn_url or self.cdn_url
        self.static_cdn_url = static_cdn_url or self.cdn_url
        self.private_files = private_files
        self.cache_control = cache_control or DEFAULT_CACHE_CONTROL
        self.options = kwargs

        # Set up the local fallback storage
        self.local_storage = FileSystemStorage(
            location=location,
            base_url=base_url,
            file_permissions_mode=file_permissions_mode,
            directory_permissions_mode=directory_permissions_mode,
        )

        # Set up the remote storage if needed
        self._setup_remote_storage()

    def _setup_remote_storage(self):
        """Set up the remote storage backend based on provider"""
        if self.provider == "cloudfront" or self.provider == "s3":
            # Create an S3Boto3Storage instance
            if not DEFAULT_AWS_STORAGE_BUCKET_NAME:
                raise ImproperlyConfigured(
                    "AWS_STORAGE_BUCKET_NAME must be set when using CloudFront or S3 storage"
                )

            # Define S3 options
            s3_options = {"bucket_name": DEFAULT_AWS_STORAGE_BUCKET_NAME}

            # Add S3 region if specified
            if DEFAULT_S3_REGION_NAME:
                s3_options["region_name"] = DEFAULT_S3_REGION_NAME

            # Add S3 custom domain if specified
            if DEFAULT_S3_CUSTOM_DOMAIN:
                s3_options["custom_domain"] = DEFAULT_S3_CUSTOM_DOMAIN

            # Add ACL settings based on privacy
            s3_options["default_acl"] = "private" if self.private_files else "public-read"

            # Add any additional options passed to the constructor
            s3_options.update(
                {
                    k: v
                    for k, v in self.options.items()
                    if k
                    in [
                        "bucket_name",
                        "region_name",
                        "custom_domain",
                        "access_key",
                        "secret_key",
                        "file_overwrite",
                        "object_parameters",
                        "querystring_auth",
                        "signature_version",
                        "location",
                    ]
                }
            )

            # Create the S3 storage instance
            self.remote_storage = S3Boto3Storage(**s3_options)
        else:
            # For other providers, we just use local storage with CDN URLs
            self.remote_storage = self.local_storage

    def _open(self, name, mode="rb"):
        """
        Open a file using the appropriate storage backend

        Args:
            name: File name
            mode: File open mode

        Returns:
            Opened file object
        """
        # Try to open from remote storage first
        try:
            return self.remote_storage._open(name, mode)
        except Exception as e:
            # Fall back to local storage
            return self.local_storage._open(name, mode)

    def _save(self, name, content):
        """
        Save a file using the appropriate storage backend

        Args:
            name: File name
            content: File content

        Returns:
            Saved file name
        """
        # Save to remote storage
        name = self.remote_storage._save(name, content)

        # Also save to local storage as backup/cache
        try:
            self.local_storage._save(name, content)
        except Exception:
            pass

        return name

    def url(self, name):
        """
        Generate a URL for the given file

        Args:
            name: File name

        Returns:
            Full URL to the file
        """
        if self.provider == "cloudfront" and self.private_files and CF_KEY_ID and CF_PRIVATE_KEY:
            # Generate signed CloudFront URL for private files
            return self._generate_cloudfront_signed_url(name)
        elif self.provider == "akamai" and self.private_files and AKAMAI_TOKEN_KEY:
            # Generate signed Akamai URL for private files
            return self._generate_akamai_signed_url(name)
        elif self.media_cdn_url:
            # Generate CDN URL for the file
            return urljoin(self.media_cdn_url, filepath_to_uri(name))
        else:
            # Fall back to remote storage URL
            return self.remote_storage.url(name)

    def path(self, name):
        """
        Return the local file system path for a file

        Args:
            name: File name

        Returns:
            Local file system path
        """
        return self.local_storage.path(name)

    def exists(self, name):
        """
        Check if a file exists

        Args:
            name: File name

        Returns:
            Boolean indicating existence
        """
        # Check remote storage first
        remote_exists = self.remote_storage.exists(name)
        if remote_exists:
            return True

        # Fall back to local storage
        return self.local_storage.exists(name)

    def size(self, name):
        """
        Return the size of a file in bytes

        Args:
            name: File name

        Returns:
            File size in bytes
        """
        try:
            return self.remote_storage.size(name)
        except Exception:
            return self.local_storage.size(name)

    def delete(self, name):
        """
        Delete a file

        Args:
            name: File name
        """
        # Delete from both storage backends
        try:
            self.remote_storage.delete(name)
        except Exception:
            pass

        try:
            self.local_storage.delete(name)
        except Exception:
            pass

    def get_accessed_time(self, name):
        """Get the last accessed time of the file"""
        return self.local_storage.get_accessed_time(name)

    def get_created_time(self, name):
        """Get the creation time of the file"""
        return self.local_storage.get_created_time(name)

    def get_modified_time(self, name):
        """Get the last modified time of the file"""
        try:
            return self.remote_storage.get_modified_time(name)
        except Exception:
            return self.local_storage.get_modified_time(name)

    def listdir(self, path):
        """List the contents of a directory"""
        try:
            return self.remote_storage.listdir(path)
        except Exception:
            return self.local_storage.listdir(path)

    def _generate_cloudfront_signed_url(self, name, expires=None):
        """
        Generate a signed CloudFront URL for private files

        Args:
            name: File name
            expires: Expiration time (seconds since epoch)

        Returns:
            Signed URL
        """
        if not all([CF_KEY_ID, CF_PRIVATE_KEY]):
            # Fall back to unsigned URL if credentials are missing
            return self.remote_storage.url(name)

        # Use default expiration if not provided
        if expires is None:
            expires = int(time.time() + DEFAULT_MAX_AGE)

        # Parse the URL to sign
        file_url = urljoin(self.media_cdn_url, filepath_to_uri(name))
        url_parts = urlparse(file_url)

        # Create the policy statement
        policy = {
            "Statement": [
                {
                    "Resource": file_url,
                    "Condition": {"DateLessThan": {"AWS:EpochTime": expires}},
                }
            ]
        }

        # Sign the policy - this is just a stub, real implementation is more complex
        # In production, you would use a proper CloudFront signing library
        # This is simplified for example purposes
        signature = "Example_Signature"

        # Add signature parameters to the URL
        query_params = {
            "Key-Pair-Id": CF_KEY_ID,
            "Expires": str(expires),
            "Signature": signature,
        }

        # Rebuild the URL with the signature parameters
        url = urlunparse(
            (
                url_parts.scheme,
                url_parts.netloc,
                url_parts.path,
                url_parts.params,
                urlencode(query_params),
                url_parts.fragment,
            )
        )

        return url

    def _generate_akamai_signed_url(self, name, expires=None):
        """
        Generate a signed Akamai URL for private files

        Args:
            name: File name
            expires: Expiration time (seconds since epoch)

        Returns:
            Signed URL
        """
        if not AKAMAI_TOKEN_KEY:
            # Fall back to unsigned URL if credentials are missing
            return urljoin(self.media_cdn_url, filepath_to_uri(name))

        # Use default expiration if not provided
        if expires is None:
            expires = int(time.time() + DEFAULT_MAX_AGE)

        # Get the file URL
        file_url = urljoin(self.media_cdn_url, filepath_to_uri(name))

        # Generate the token
        # This is a simplified example - real Akamai token generation is more complex
        token_name = "__token__"
        ip = ""  # IP restriction (empty for no restriction)
        start_time = int(time.time())
        window = expires - start_time
        acl = "*"  # Access control - * means any URL under the path

        # Create the token data
        token_data = f"st={start_time}&exp={expires}&ip={ip}&acl={acl}"

        # Sign the token - this is just an example
        # In production, you would use a proper Akamai signing library
        key = base64.b64decode(AKAMAI_TOKEN_KEY)

        if AKAMAI_TOKEN_ALGO == "sha256":
            token_hmac = hmac.new(key, token_data.encode("utf-8"), hashlib.sha256)
        else:
            token_hmac = hmac.new(key, token_data.encode("utf-8"), hashlib.sha1)

        token_signature = base64.b64encode(token_hmac.digest()).decode("utf-8")
        token = f"{token_data}&hmac={token_signature}"

        # Add the token to the URL
        if "?" in file_url:
            signed_url = f"{file_url}&{token_name}={token}"
        else:
            signed_url = f"{file_url}?{token_name}={token}"

        return signed_url

    def get_available_name(self, name, max_length=None):
        """
        Get an available file name, avoiding duplicates

        Args:
            name: Desired file name
            max_length: Maximum length of the file name

        Returns:
            Available file name
        """
        return self.remote_storage.get_available_name(name, max_length)

    # Consistency and performance methods

    def purge_file(self, name):
        """
        Purge a file from the CDN cache

        Args:
            name: File name

        Returns:
            Boolean indicating success
        """
        # This would integrate with the CDN's API to purge a specific file
        # Implementation depends on the CDN provider
        # This is a simplified example that always succeeds
        return True

    def clear_cache(self, patterns=None):
        """
        Clear the CDN cache for multiple files

        Args:
            patterns: List of file patterns to clear

        Returns:
            Boolean indicating success
        """
        # This would integrate with the CDN's API to clear the cache
        # Implementation depends on the CDN provider
        # This is a simplified example that always succeeds
        return True

    def get_cache_control(self, name):
        """
        Get the Cache-Control header for a file

        Args:
            name: File name

        Returns:
            Cache-Control header value
        """
        # Use different cache settings based on file type
        ext = os.path.splitext(name)[1].lower()

        # Media files can be cached longer
        if ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]:
            return "public, max-age=604800"  # 7 days

        # Videos can be cached even longer
        if ext in [".mp4", ".webm"]:
            return "public, max-age=2592000"  # 30 days

        # Default cache setting
        return self.cache_control


@deconstructible
class MediaCDNStorage(CDNStorage):
    """
    CDN storage specifically configured for media files.
    """

    def __init__(self, **kwargs):
        """Initialize with appropriate media-specific settings"""
        kwargs.setdefault("location", settings.MEDIA_ROOT)
        kwargs.setdefault("base_url", DEFAULT_MEDIA_URL)
        kwargs.setdefault("cdn_url", kwargs.get("media_cdn_url", DEFAULT_CDN_URL))

        super().__init__(**kwargs)

    @cached_property
    def cdn_enabled(self):
        """Check if CDN is properly configured for media"""
        return bool(self.cdn_url or (DEFAULT_AWS_STORAGE_BUCKET_NAME and DEFAULT_S3_CUSTOM_DOMAIN))


@deconstructible
class StaticCDNStorage(CDNStorage):
    """
    CDN storage specifically configured for static files.
    """

    def __init__(self, **kwargs):
        """Initialize with appropriate static-specific settings"""
        kwargs.setdefault("location", settings.STATIC_ROOT)
        kwargs.setdefault("base_url", DEFAULT_STATIC_URL)
        kwargs.setdefault("cdn_url", kwargs.get("static_cdn_url", DEFAULT_CDN_URL))
        kwargs.setdefault("cache_control", "public, max-age=31536000")  # 1 year

        super().__init__(**kwargs)

    @cached_property
    def cdn_enabled(self):
        """Check if CDN is properly configured for static files"""
        return bool(self.cdn_url or (DEFAULT_AWS_STORAGE_BUCKET_NAME and DEFAULT_S3_CUSTOM_DOMAIN))


class DynamicResizingStorage(MediaCDNStorage):
    """
    Storage class that supports dynamic image resizing via URL parameters.
    """

    def url(self, name):
        """
        Generate a URL for the given file, with optional resizing

        Args:
            name: File name

        Returns:
            Full URL to the file
        """
        # Get base URL
        base_url = super().url(name)

        # Check if this is an image file
        ext = os.path.splitext(name)[1].lower()
        if ext not in [".jpg", ".jpeg", ".png", ".gif", ".webp"]:
            return base_url

        # Get resize settings from thread local
        from threading import local

        _local = local()

        resize_width = getattr(_local, "resize_width", None)
        resize_height = getattr(_local, "resize_height", None)
        resize_mode = getattr(_local, "resize_mode", "fit")

        # Clear settings
        for attr in ["resize_width", "resize_height", "resize_mode"]:
            if hasattr(_local, attr):
                delattr(_local, attr)

        # If no resize needed, return base URL
        if not resize_width and not resize_height:
            return base_url

        # Add resize parameters to URL
        params = {}
        if resize_width:
            params["w"] = resize_width
        if resize_height:
            params["h"] = resize_height
        if resize_mode:
            params["mode"] = resize_mode

        # Add parameters to URL
        url_parts = urlparse(base_url)
        query = urlencode(params)

        # Rebuild URL with parameters
        return urlunparse(
            (
                url_parts.scheme,
                url_parts.netloc,
                url_parts.path,
                url_parts.params,
                query,
                url_parts.fragment,
            )
        )

    @staticmethod
    def resize(width=None, height=None, mode="fit"):
        """
        Set resize parameters for the next URL generation

        Args:
            width: Target width
            height: Target height
            mode: Resize mode ('fit', 'fill', or 'crop')

        Returns:
            The storage instance (for method chaining)
        """
        from threading import local

        _local = local()

        if width:
            _local.resize_width = width
        if height:
            _local.resize_height = height
        if mode:
            _local.resize_mode = mode

        return DynamicResizingStorage()


# Default storage instances
media_cdn_storage = MediaCDNStorage()
static_cdn_storage = StaticCDNStorage()
dynamic_image_storage = DynamicResizingStorage()
