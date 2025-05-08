import os
import tempfile
import uuid
from io import BytesIO

from PIL import Image

from core.storage.s3_storage import S3Storage


class StoryMediaService:
    """
    Service for processing and storing story media files (images and videos).
    Handles:
    - Uploading images/videos to S3
    - Creating thumbnails for videos
    - Optimizing images for web display
    - Setting proper content types for media
    """

    def __init__(self):
        self.s3_storage = S3Storage()
        self.max_image_size = (1080, 1920)  # Max dimensions for story images
        self.thumbnail_size = (320, 568)  # Size for thumbnails

    def process_story_media(self, media_file, story_type, shop_id):
        """
        Process a story media file (image or video)

        Args:
            media_file (InMemoryUploadedFile): The uploaded file
            story_type (str): Type of story ('image' or 'video')
            shop_id (uuid): ID of the shop creating the story

        Returns:
            dict: Dictionary with media_url and thumbnail_url (for videos)
        """
        if story_type == "image":
            return self._process_image(media_file, shop_id)
        elif story_type == "video":
            return self._process_video(media_file, shop_id)
        else:
            raise ValueError(f"Unsupported story type: {story_type}")

    def _process_image(self, image_file, shop_id):
        """
        Process an image file:
        - Resize if necessary
        - Optimize for web
        - Upload to S3

        Args:
            image_file (InMemoryUploadedFile): The uploaded image
            shop_id (uuid): ID of the shop creating the story

        Returns:
            dict: Dictionary with media_url
        """
        # Open the image
        try:
            img = Image.open(image_file)

            # Convert to RGB if needed
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")

            # Resize if larger than max dimensions
            if (
                img.width > self.max_image_size[0]
                or img.height > self.max_image_size[1]
            ):
                img.thumbnail(self.max_image_size, Image.LANCZOS)

            # Save optimized image to BytesIO
            optimized = BytesIO()
            img.save(optimized, format="JPEG", quality=85, optimize=True)
            optimized.seek(0)

            # Generate path and upload to S3
            filename = f"{uuid.uuid4()}.jpg"
            s3_path = f"stories/{shop_id}/images/{filename}"

            media_url = self.s3_storage.upload_file(
                optimized, s3_path, content_type="image/jpeg"
            )

            return {"media_url": media_url}

        except Exception as e:
            # Log error
            print(f"Error processing image: {e}")
            raise

    def _process_video(self, video_file, shop_id):
        """
        Process a video file:
        - Create thumbnail
        - Upload video to S3
        - Upload thumbnail to S3

        Args:
            video_file (InMemoryUploadedFile): The uploaded video
            shop_id (uuid): ID of the shop creating the story

        Returns:
            dict: Dictionary with media_url and thumbnail_url
        """
        # Create temporary file to work with
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            for chunk in video_file.chunks():
                temp_file.write(chunk)
            temp_file_path = temp_file.name

        try:
            # Generate thumbnail from video (using first frame)
            thumbnail = self._generate_video_thumbnail(temp_file_path)

            # Generate paths and upload to S3
            video_filename = f"{uuid.uuid4()}.mp4"
            thumbnail_filename = f"{uuid.uuid4()}.jpg"

            video_s3_path = f"stories/{shop_id}/videos/{video_filename}"
            thumbnail_s3_path = f"stories/{shop_id}/thumbnails/{thumbnail_filename}"

            # Upload video
            with open(temp_file_path, "rb") as video_data:
                media_url = self.s3_storage.upload_file(
                    video_data, video_s3_path, content_type="video/mp4"
                )

            # Upload thumbnail
            thumbnail_url = self.s3_storage.upload_file(
                thumbnail, thumbnail_s3_path, content_type="image/jpeg"
            )

            return {"media_url": media_url, "thumbnail_url": thumbnail_url}

        except Exception as e:
            # Log error
            print(f"Error processing video: {e}")
            raise
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    def _generate_video_thumbnail(self, video_path):
        """
        Generate a thumbnail from a video using ffmpeg or similar

        Args:
            video_path (str): Path to the video file

        Returns:
            BytesIO: Thumbnail image data
        """
        try:
            # This is a simplified version - in a real implementation,
            # you would use a library like opencv or ffmpeg to extract
            # a frame and create a thumbnail

            # For this example, we'll use a placeholder
            # In a real implementation, replace this with actual code to
            # extract a frame from the video

            # Create a blank image for demonstration
            thumbnail = Image.new("RGB", self.thumbnail_size, color="gray")

            # Save to BytesIO
            thumbnail_data = BytesIO()
            thumbnail.save(thumbnail_data, format="JPEG", quality=85)
            thumbnail_data.seek(0)

            return thumbnail_data

        except Exception as e:
            # Log error
            print(f"Error generating video thumbnail: {e}")
            raise
