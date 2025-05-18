import logging
import mimetypes
from io import BytesIO

from PIL import Image

from core.storage.s3_storage import S3Storage

logger = logging.getLogger("chatapp.services")


class MediaService:
    """Service for handling media uploads in chat"""

    @staticmethod
    def upload_chat_media(file_obj, conversation_id, media_type="image"):
        """
        Upload media file to S3 storage

        Parameters:
        - file_obj: File object to upload
        - conversation_id: ID of the conversation
        - media_type: Type of media ('image' or 'video')

        Returns:
        - URL of uploaded file
        """
        if not file_obj:
            logger.error("No file provided for upload")
            return None

        # Validate file type
        if media_type == "image":
            valid_types = ["image/jpeg", "image/png", "image/gif"]
        elif media_type == "video":
            valid_types = ["video/mp4", "video/quicktime", "video/mpeg"]
        else:
            logger.error(f"Invalid media type: {media_type}")
            return None

        # Detect content type
        content_type = getattr(file_obj, "content_type", None)
        if not content_type:
            # Try to guess from filename
            content_type, _ = mimetypes.guess_type(file_obj.name)

        if not content_type or content_type not in valid_types:
            logger.error(f"Invalid file type: {content_type}")
            return None

        # Process image if needed (resize large images)
        if media_type == "image" and content_type in ["image/jpeg", "image/png"]:
            file_obj = MediaService._process_image(file_obj)

        # Generate path in S3
        s3_path = f"chat/{conversation_id}/{media_type}s/"

        # Upload to S3
        try:
            s3_storage = S3Storage()
            media_url = s3_storage.upload_file(file_obj, s3_path)
            return media_url
        except Exception as e:
            logger.error(f"Error uploading media to S3: {str(e)}")
            return None

    @staticmethod
    def _process_image(file_obj, max_size=(1200, 1200)):
        """Resize image if it's too large"""
        try:
            # Open image
            img = Image.open(file_obj)

            # Check if resize needed
            if img.width > max_size[0] or img.height > max_size[1]:
                # Preserve aspect ratio
                img.thumbnail(max_size, Image.LANCZOS)

                # Save to buffer
                output = BytesIO()
                format = img.format or "JPEG"
                img.save(output, format=format, quality=85)

                # Reset buffer position
                output.seek(0)

                # Add name attribute for S3 storage
                output.name = file_obj.name

                return output

            # Reset file position
            file_obj.seek(0)
            return file_obj

        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            file_obj.seek(0)  # Reset position
            return file_obj

    @staticmethod
    def delete_chat_media(media_url):
        """Delete media file from S3 storage"""
        if not media_url:
            return False

        try:
            s3_storage = S3Storage()
            return s3_storage.delete_file(media_url)
        except Exception as e:
            logger.error(f"Error deleting media from S3: {str(e)}")
            return False
