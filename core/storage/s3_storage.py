"""
AWS S3 storage integration for the Queue Me platform.

This module provides a comprehensive interface to AWS S3 for storing and
retrieving media files.
"""

import logging
import mimetypes
import os
import uuid
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError
from django.conf import settings

logger = logging.getLogger(__name__)


class S3Storage:
    """
    AWS S3 storage implementation.

    This class provides methods to upload, download, and manage files in S3.
    """

    def __init__(self):
        """Initialize S3 client."""
        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
        )
        self.bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        self.s3_domain = (
            f"{self.bucket_name}.s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com"
        )

        if hasattr(settings, "AWS_S3_CUSTOM_DOMAIN"):
            self.custom_domain = settings.AWS_S3_CUSTOM_DOMAIN
        else:
            self.custom_domain = None

    def upload_file(
        self, file_obj, path_prefix="", filename=None, content_type=None, public=True
    ):
        """
        Upload file to S3 bucket.

        Args:
            file_obj: File object or path to file
            path_prefix (str): Path prefix within bucket
            filename (str): Custom filename (default: generate UUID)
            content_type (str): Content type (default: auto-detect)
            public (bool): Whether the file should be publicly accessible

        Returns:
            str: URL of uploaded file
        """
        try:
            # Generate unique filename if not provided
            if not filename:
                if hasattr(file_obj, "name"):
                    original_filename = file_obj.name
                    ext = os.path.splitext(original_filename)[1].lower()
                else:
                    ext = ""
                filename = f"{uuid.uuid4()}{ext}"

            # Combine with path prefix
            s3_path = (
                f"{path_prefix.rstrip('/')}/{filename}" if path_prefix else filename
            )

            # Get content type if not provided
            if not content_type and hasattr(file_obj, "name"):
                content_type = mimetypes.guess_type(file_obj.name)[0]

            if not content_type:
                content_type = "application/octet-stream"

            # Upload extra args
            extra_args = {
                "ContentType": content_type,
            }

            # Set ACL if file should be public
            if public:
                extra_args["ACL"] = "public-read"

            # Handle different file object types
            if hasattr(file_obj, "read"):
                # File-like object
                self.s3_client.upload_fileobj(
                    file_obj, self.bucket_name, s3_path, ExtraArgs=extra_args
                )
            else:
                # Assume it's a file path
                self.s3_client.upload_file(
                    file_obj, self.bucket_name, s3_path, ExtraArgs=extra_args
                )

            # Return public URL
            if self.custom_domain:
                return f"https://{self.custom_domain}/{s3_path}"
            else:
                return f"https://{self.s3_domain}/{s3_path}"

        except ClientError as e:
            logger.error(f"Error uploading file to S3: {e}")
            raise

    def delete_file(self, file_url_or_key):
        """
        Delete file from S3 bucket.

        Args:
            file_url_or_key (str): File URL or S3 key

        Returns:
            bool: Success status
        """
        try:
            # Extract key from URL if needed
            if file_url_or_key.startswith("http"):
                parsed_url = urlparse(file_url_or_key)
                # Remove leading slash
                path = parsed_url.path.lstrip("/")
            else:
                path = file_url_or_key

            # Delete file
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=path)

            logger.info(f"Deleted file from S3: {path}")
            return True

        except ClientError as e:
            logger.error(f"Error deleting file from S3: {e}")
            return False

    def get_file(self, file_key):
        """
        Get file from S3 bucket.

        Args:
            file_key (str): S3 key

        Returns:
            bytes: File content
        """
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=file_key)
            return response["Body"].read()

        except ClientError as e:
            logger.error(f"Error getting file from S3: {e}")
            raise

    def get_presigned_url(self, file_key, expiration=3600):
        """
        Generate a presigned URL for a file.

        Args:
            file_key (str): S3 key
            expiration (int): URL expiration in seconds

        Returns:
            str: Presigned URL
        """
        try:
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": file_key},
                ExpiresIn=expiration,
            )
            return url

        except ClientError as e:
            logger.error(f"Error generating presigned URL: {e}")
            raise

    def list_files(self, prefix=""):
        """
        List files in S3 bucket with given prefix.

        Args:
            prefix (str): Path prefix

        Returns:
            list: List of file keys
        """
        try:
            paginator = self.s3_client.get_paginator("list_objects_v2")
            page_iterator = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix)

            files = []
            for page in page_iterator:
                if "Contents" in page:
                    for obj in page["Contents"]:
                        files.append(obj["Key"])

            return files

        except ClientError as e:
            logger.error(f"Error listing files in S3: {e}")
            raise

    def file_exists(self, file_key):
        """
        Check if file exists in S3 bucket.

        Args:
            file_key (str): S3 key

        Returns:
            bool: Whether file exists
        """
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=file_key)
            return True

        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            else:
                logger.error(f"Error checking if file exists in S3: {e}")
                raise

    def copy_file(self, source_key, dest_key):
        """
        Copy file within S3 bucket.

        Args:
            source_key (str): Source S3 key
            dest_key (str): Destination S3 key

        Returns:
            bool: Success status
        """
        try:
            self.s3_client.copy_object(
                Bucket=self.bucket_name,
                CopySource={"Bucket": self.bucket_name, "Key": source_key},
                Key=dest_key,
            )

            logger.info(f"Copied file in S3: {source_key} -> {dest_key}")
            return True

        except ClientError as e:
            logger.error(f"Error copying file in S3: {e}")
            return False

    def get_file_size(self, file_key):
        """
        Get file size in S3 bucket.

        Args:
            file_key (str): S3 key

        Returns:
            int: File size in bytes
        """
        try:
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=file_key)
            return response["ContentLength"]

        except ClientError as e:
            logger.error(f"Error getting file size from S3: {e}")
            raise
