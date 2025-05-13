import os
import tempfile
import uuid

import ffmpeg
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from core.storage.s3_storage import S3Storage

from ..exceptions import VideoProcessingError
from ..models import Reel
from ..tasks import process_reel_video as process_reel_video_task


class ReelService:
    """Service for managing reels and video processing"""

    @staticmethod
    def create_reel(shop, data):
        """
        Create a new reel with all related data

        Args:
            shop: Shop instance that owns the reel
            data: Dictionary with reel data

        Returns:
            Created Reel instance
        """
        video = data.pop("video", None)
        thumbnail = data.pop("thumbnail", None)
        service_ids = data.pop("service_ids", [])
        package_ids = data.pop("package_ids", [])
        category_ids = data.pop("category_ids", [])

        # Set shop and city
        data["shop"] = shop
        if shop.location:
            data["city"] = shop.location.city

        with transaction.atomic():
            # Create reel
            reel = Reel.objects.create(**data)

            # Add video if provided
            if video:
                reel.video = video
                reel.processing_status = "processing"
                reel.save(update_fields=["video", "processing_status"])

                # Process video asynchronously
                process_reel_video_task.delay(str(reel.id))

            # Add thumbnail if provided
            if thumbnail:
                reel.thumbnail = thumbnail
                reel.save(update_fields=["thumbnail"])

            # Add relationships
            if service_ids:
                reel.services.add(*service_ids)

            if package_ids:
                reel.packages.add(*package_ids)

            if category_ids:
                reel.categories.add(*category_ids)

        return reel

    @staticmethod
    def update_reel(reel, data):
        """
        Update an existing reel

        Args:
            reel: Reel instance to update
            data: Dictionary with updated reel data

        Returns:
            Updated Reel instance
        """
        video = data.pop("video", None)
        thumbnail = data.pop("thumbnail", None)
        service_ids = data.pop("service_ids", None)
        package_ids = data.pop("package_ids", None)
        category_ids = data.pop("category_ids", None)

        with transaction.atomic():
            # Update basic fields
            for key, value in data.items():
                setattr(reel, key, value)

            # Process new video if provided
            if video:
                reel.video = video
                reel.processing_status = "processing"

                # Process video asynchronously
                process_reel_video_task.delay(str(reel.id))

            # Update thumbnail if provided
            if thumbnail:
                reel.thumbnail = thumbnail

            reel.save()

            # Update relationships if provided
            if service_ids is not None:
                reel.services.set(service_ids)

            if package_ids is not None:
                reel.packages.set(package_ids)

            if category_ids is not None:
                reel.categories.set(category_ids)

        return reel

    @staticmethod
    def publish_reel(reel_id):
        """
        Publish a draft reel

        Args:
            reel_id: UUID of the reel to publish

        Returns:
            Published Reel instance
        """
        reel = Reel.objects.get(id=reel_id)

        # Verify reel can be published
        if reel.status != "draft":
            raise ValueError("Only draft reels can be published")

        if not reel.services.exists() and not reel.packages.exists():
            raise ValueError("At least one service or package must be linked before publishing")

        # Publish reel
        reel.status = "published"
        reel.published_at = timezone.now()
        reel.save(update_fields=["status", "published_at"])

        return reel

    @staticmethod
    def archive_reel(reel_id):
        """
        Archive a published reel

        Args:
            reel_id: UUID of the reel to archive

        Returns:
            Archived Reel instance
        """
        reel = Reel.objects.get(id=reel_id)

        # Verify reel can be archived
        if reel.status != "published":
            raise ValueError("Only published reels can be archived")

        # Archive reel
        reel.status = "archived"
        reel.save(update_fields=["status"])

        return reel

    @staticmethod
    def process_reel_video(reel):
        """
        Process a reel's video to:
        1. Extract duration
        2. Generate thumbnail if not provided
        3. Optimize for streaming

        Args:
            reel: Reel instance with video to process

        Returns:
            Updated Reel instance
        """
        if not reel.video:
            return reel

        try:
            # Check if video file exists and is accessible
            if not os.path.exists(reel.video.path):
                reel.processing_status = "failed"
                reel.save(update_fields=["processing_status"])
                raise VideoProcessingError("Video file not found")

            # Get video info
            probe = ffmpeg.probe(reel.video.path)
            video_info = next(
                (stream for stream in probe["streams"] if stream["codec_type"] == "video"),
                None,
            )

            if not video_info:
                reel.processing_status = "failed"
                reel.save(update_fields=["processing_status"])
                raise VideoProcessingError("No video stream found")

            # Extract duration (in seconds)
            duration = float(probe["format"]["duration"])
            reel.duration = int(duration)

            # Generate thumbnail if not already provided
            if not reel.thumbnail:
                # Take thumbnail at 1/3 of the video
                thumbnail_time = duration / 3

                # Create a temporary file for the thumbnail
                with tempfile.NamedTemporaryFile(suffix=".jpg") as temp_thumb:
                    # Extract frame as thumbnail
                    (
                        ffmpeg.input(reel.video.path, ss=thumbnail_time)
                        .filter("scale", 640, -1)  # Resize preserving aspect ratio
                        .output(temp_thumb.name, vframes=1)
                        .overwrite_output()
                        .run(quiet=True)
                    )

                    # Read the thumbnail file
                    temp_thumb.seek(0)
                    thumbnail_data = temp_thumb.read()

                    # Save the thumbnail to the model
                    thumbnail_filename = f"{uuid.uuid4()}.jpg"
                    reel.thumbnail.save(thumbnail_filename, ContentFile(thumbnail_data), save=False)

            # Update processing status
            reel.processing_status = "completed"
            reel.save()

            return reel

        except Exception as e:
            # Mark processing as failed
            reel.processing_status = "failed"
            reel.save(update_fields=["processing_status"])

            # Re-raise the exception
            raise VideoProcessingError(f"Error processing video: {str(e)}")

    @staticmethod
    def delete_reel(reel_id):
        """
        Delete a reel and all its associated files

        Args:
            reel_id: UUID of the reel to delete

        Returns:
            Boolean indicating success
        """
        try:
            reel = Reel.objects.get(id=reel_id)

            # Get file paths before deletion
            video_path = reel.video.name if reel.video else None
            thumbnail_path = reel.thumbnail.name if reel.thumbnail else None

            # Delete from S3 if using S3 storage
            if hasattr(settings, "AWS_STORAGE_BUCKET_NAME") and settings.AWS_STORAGE_BUCKET_NAME:
                s3_storage = S3Storage()

                if video_path:
                    s3_storage.delete_file(video_path)

                if thumbnail_path:
                    s3_storage.delete_file(thumbnail_path)

            # Delete the database record (will cascade to related objects)
            reel.delete()

            return True
        except Reel.DoesNotExist:
            return False
        except Exception:
            return False
