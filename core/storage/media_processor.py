"""
Media processing utilities for the Queue Me platform.

This module provides classes and functions for processing and optimizing
images and videos for the platform.
"""

import logging
import os
import re
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image, ImageOps

from core.exceptions import MediaProcessingException

from .s3_storage import S3Storage

logger = logging.getLogger("media")


# Define absolute paths to binaries used for media processing
FFMPEG_PATH = getattr(
    settings, "FFMPEG_BINARY_PATH", shutil.which("ffmpeg") or "/usr/bin/ffmpeg"
)
FFPROBE_PATH = getattr(
    settings, "FFPROBE_BINARY_PATH", shutil.which("ffprobe") or "/usr/bin/ffprobe"
)


def validate_filename(filename):
    """
    Validate that a filename is safe and contains no potential command injection characters.

    Args:
        filename: The filename to validate

    Returns:
        bool: True if the filename is safe, False otherwise
    """
    # Only allow alphanumeric characters, dots, hyphens, and underscores in filenames
    pattern = re.compile(r"^[a-zA-Z0-9._-]+$")
    return bool(pattern.match(os.path.basename(filename)))


class MediaProcessor:
    """
    Media processing utilities for images and videos.

    This class provides methods to process, optimize, and validate media files.
    """

    # Image formats supported for processing
    SUPPORTED_IMAGE_FORMATS = ["jpeg", "jpg", "png", "webp"]

    # Video formats supported for processing
    SUPPORTED_VIDEO_FORMATS = ["mp4", "mov", "avi"]

    # Default image sizes for different use cases
    IMAGE_SIZES = {
        "thumbnail": (150, 150),
        "small": (300, 300),
        "medium": (600, 600),
        "large": (1200, 1200),
        "cover": (1920, 1080),
        "profile": (400, 400),
        "avatar": (200, 200),
        "story": (1080, 1920),  # Portrait for stories
        "reel": (1080, 1920),  # Portrait for reels
    }

    def __init__(self, storage=None):
        """
        Initialize MediaProcessor.

        Args:
            storage: Storage backend (default: S3Storage)
        """
        self.storage = storage or S3Storage()

    def process_image(
        self,
        image_file,
        size_preset=None,
        max_width=None,
        max_height=None,
        quality=85,
        format=None,
        crop=False,
    ):
        """
        Process and optimize an image.

        Args:
            image_file: Image file object
            size_preset (str): Preset size name (e.g., 'thumbnail', 'medium')
            max_width (int): Maximum width
            max_height (int): Maximum height
            quality (int): JPEG/WebP quality (1-100)
            format (str): Output format (jpeg, png, webp)
            crop (bool): Whether to crop image to exact dimensions

        Returns:
            InMemoryUploadedFile: Processed image
        """
        try:
            # Get image format
            if hasattr(image_file, "name"):
                file_ext = os.path.splitext(image_file.name)[1].lower().lstrip(".")
            else:
                # Default to JPEG if format cannot be determined
                file_ext = "jpg"

            # Set output format
            output_format = format or file_ext
            if output_format not in self.SUPPORTED_IMAGE_FORMATS:
                output_format = "jpeg"

            # Convert format to PIL format
            pil_format = (
                "JPEG" if output_format in ["jpg", "jpeg"] else output_format.upper()
            )

            # Open image with PIL
            img = Image.open(image_file)

            # Apply exif orientation
            img = ImageOps.exif_transpose(img)

            # Determine target dimensions
            if size_preset and size_preset in self.IMAGE_SIZES:
                target_width, target_height = self.IMAGE_SIZES[size_preset]
            else:
                target_width = max_width
                target_height = max_height

            # Resize image
            if target_width or target_height:
                if crop and target_width and target_height:
                    # Crop to exact dimensions (center crop)
                    img = ImageOps.fit(
                        img, (target_width, target_height), method=Image.LANCZOS
                    )
                else:
                    # Resize preserving aspect ratio
                    orig_width, orig_height = img.size

                    # Calculate scale factors
                    width_scale = (
                        target_width / orig_width if target_width else float("inf")
                    )
                    height_scale = (
                        target_height / orig_height if target_height else float("inf")
                    )

                    # Use smallest scale factor to ensure both dimensions fit
                    scale = min(width_scale, height_scale)

                    # Skip if no scaling is needed
                    if scale < 1:
                        new_width = int(orig_width * scale)
                        new_height = int(orig_height * scale)
                        img = img.resize((new_width, new_height), Image.LANCZOS)

            # Convert to RGB mode if saving as JPEG or WebP
            if pil_format in ["JPEG", "WEBP"] and img.mode != "RGB":
                img = img.convert("RGB")

            # Save processed image to BytesIO
            output = BytesIO()
            if pil_format == "JPEG":
                img.save(output, format=pil_format, quality=quality, optimize=True)
            elif pil_format == "PNG":
                img.save(output, format=pil_format, optimize=True)
            elif pil_format == "WEBP":
                img.save(output, format=pil_format, quality=quality)
            else:
                img.save(output, format=pil_format)

            # Get file size
            output.seek(0)
            size = len(output.getvalue())

            # Create new filename
            if hasattr(image_file, "name"):
                filename = os.path.basename(image_file.name)
                name, ext = os.path.splitext(filename)
                new_filename = f"{name}.{output_format}"
            else:
                new_filename = f"image.{output_format}"

            # Create InMemoryUploadedFile from processed image
            output.seek(0)
            content_type = f"image/{output_format.replace('jpg', 'jpeg')}"
            processed_image = InMemoryUploadedFile(
                output, "ImageField", new_filename, content_type, size, None
            )

            logger.info(f"Processed image {new_filename}, size: {size} bytes")
            return processed_image

        except Exception as e:
            logger.error(f"Error processing image: {e}")
            raise MediaProcessingException(f"Error processing image: {e}")

    def generate_image_variations(self, image_file, variations=None):
        """
        Generate multiple variations of an image.

        Args:
            image_file: Image file object
            variations (dict): Dictionary of variation names and size presets

        Returns:
            dict: Dictionary of processed images
        """
        if variations is None:
            variations = {
                "thumbnail": "thumbnail",
                "medium": "medium",
                "large": "large",
            }

        processed_images = {}

        with ThreadPoolExecutor() as executor:
            futures = {}
            for name, preset in variations.items():
                futures[name] = executor.submit(
                    self.process_image, image_file, size_preset=preset
                )

            for name, future in futures.items():
                try:
                    processed_images[name] = future.result()
                except Exception as e:
                    logger.error(f"Error generating image variation '{name}': {e}")

        return processed_images

    def process_video(
        self, video_file, max_size_mb=10, max_duration=60, generate_thumbnail=True
    ):
        """
        Process a video file.

        Args:
            video_file: Video file object
            max_size_mb (int): Maximum file size in MB
            max_duration (int): Maximum duration in seconds
            generate_thumbnail (bool): Whether to generate a thumbnail

        Returns:
            tuple: (Processed video file, thumbnail file or None)
        """
        # Check if ffmpeg is available
        if not os.path.isfile(FFMPEG_PATH) or not os.access(FFMPEG_PATH, os.X_OK):
            logger.warning(
                f"ffmpeg not available at {FFMPEG_PATH}, skipping video processing"
            )
            return video_file, None

        try:
            # Create temp file for input with a secure random name
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_in:
                # Write input file to temp file
                for chunk in video_file.chunks():
                    tmp_in.write(chunk)
                tmp_in.flush()
                input_path = tmp_in.name

            # Get video info using absolute path to ffprobe
            cmd = [
                FFPROBE_PATH,
                "-v",
                "error",
                "-show_entries",
                "format=duration,size",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                input_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            info = result.stdout.strip().split("\n")

            if len(info) >= 2:
                duration = float(info[0])
                size_bytes = int(info[1])
                size_mb = size_bytes / (1024 * 1024)

                # Check duration
                if duration > max_duration:
                    raise MediaProcessingException(
                        f"Video duration ({duration:.1f}s) exceeds maximum ({max_duration}s)"
                    )

                # Check size
                if size_mb > max_size_mb:
                    logger.info(
                        f"Video size ({size_mb:.1f}MB) exceeds target ({max_size_mb}MB), compressing"
                    )

                    # Create temp file for output with a secure random name
                    with tempfile.NamedTemporaryFile(
                        delete=False, suffix=".mp4"
                    ) as tmp_out:
                        output_path = tmp_out.name

                    # Compress video using absolute path to ffmpeg
                    bitrate = int((max_size_mb * 8192) / duration)  # Convert to kbps
                    cmd = [
                        FFMPEG_PATH,
                        "-i",
                        input_path,
                        "-c:v",
                        "libx264",
                        "-crf",
                        "28",
                        "-maxrate",
                        f"{bitrate}k",
                        "-bufsize",
                        f"{bitrate*2}k",
                        "-c:a",
                        "aac",
                        "-b:a",
                        "128k",
                        output_path,
                    ]
                    subprocess.run(cmd, capture_output=True, check=True)

                    # Read compressed video
                    with open(output_path, "rb") as f:
                        processed_video = ContentFile(f.read())

                    # Set name (sanitized)
                    if hasattr(video_file, "name"):
                        # Sanitize the filename
                        safe_name = os.path.basename(video_file.name)
                        if not validate_filename(safe_name):
                            safe_name = "video.mp4"
                        processed_video.name = safe_name
                    else:
                        processed_video.name = "video.mp4"

                    # Clean up
                    os.unlink(output_path)
                else:
                    # No need to compress
                    processed_video = video_file
            else:
                # Couldn't get info, skip processing
                processed_video = video_file

            # Generate thumbnail if requested
            thumbnail = None
            if generate_thumbnail:
                # Create temp file for thumbnail with a secure random name
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=".jpg"
                ) as tmp_thumb:
                    thumbnail_path = tmp_thumb.name

                # Extract thumbnail at 1 second using absolute path to ffmpeg
                cmd = [
                    FFMPEG_PATH,
                    "-i",
                    input_path,
                    "-ss",
                    "00:00:01.000",
                    "-vframes",
                    "1",
                    "-vf",
                    "scale=600:-1",
                    thumbnail_path,
                ]
                subprocess.run(cmd, capture_output=True, check=True)

                # Read thumbnail
                with open(thumbnail_path, "rb") as f:
                    thumbnail = ContentFile(f.read())

                # Set name (sanitized)
                if hasattr(video_file, "name"):
                    # Sanitize the filename
                    name = os.path.splitext(os.path.basename(video_file.name))[0]
                    if not validate_filename(name):
                        name = "video"
                    thumbnail.name = f"{name}_thumbnail.jpg"
                else:
                    thumbnail.name = "video_thumbnail.jpg"

                # Clean up
                os.unlink(thumbnail_path)

            # Clean up input file
            os.unlink(input_path)

            return processed_video, thumbnail

        except subprocess.CalledProcessError as e:
            logger.error(f"Error processing video with ffmpeg: {e}")
            raise MediaProcessingException(f"Error processing video: {e}")
        except Exception as e:
            logger.error(f"Error processing video: {e}")
            raise MediaProcessingException(f"Error processing video: {e}")

    def validate_image(
        self,
        image_file,
        min_dimensions=None,
        max_dimensions=None,
        max_size_mb=5,
        allowed_formats=None,
    ):
        """
        Validate an image file.

        Args:
            image_file: Image file object
            min_dimensions (tuple): Minimum width and height
            max_dimensions (tuple): Maximum width and height
            max_size_mb (int): Maximum file size in MB
            allowed_formats (list): List of allowed formats

        Returns:
            bool: True if valid, False otherwise

        Raises:
            MediaProcessingException: If validation fails
        """
        try:
            # Check format
            if hasattr(image_file, "name"):
                file_ext = os.path.splitext(image_file.name)[1].lower().lstrip(".")
                if allowed_formats and file_ext not in allowed_formats:
                    raise MediaProcessingException(
                        f"Image format '{file_ext}' not allowed. Allowed formats: {', '.join(allowed_formats)}"
                    )

            # Check file size
            if hasattr(image_file, "size"):
                size_mb = image_file.size / (1024 * 1024)
                if size_mb > max_size_mb:
                    raise MediaProcessingException(
                        f"Image size ({size_mb:.1f}MB) exceeds maximum ({max_size_mb}MB)"
                    )

            # Open with PIL to check dimensions
            img = Image.open(image_file)
            width, height = img.size

            # Check minimum dimensions
            if min_dimensions:
                min_width, min_height = min_dimensions
                if width < min_width or height < min_height:
                    raise MediaProcessingException(
                        f"Image dimensions ({width}x{height}) below minimum ({min_width}x{min_height})"
                    )

            # Check maximum dimensions
            if max_dimensions:
                max_width, max_height = max_dimensions
                if width > max_width or height > max_height:
                    raise MediaProcessingException(
                        f"Image dimensions ({width}x{height}) exceed maximum ({max_width}x{max_height})"
                    )

            # Seek to beginning of file for future processing
            if hasattr(image_file, "seek"):
                image_file.seek(0)

            return True

        except MediaProcessingException:
            # Re-raise known exceptions
            raise
        except Exception as e:
            logger.error(f"Error validating image: {e}")
            raise MediaProcessingException(f"Invalid image file: {e}")

    def validate_video(
        self, video_file, max_size_mb=10, max_duration=60, allowed_formats=None
    ):
        """
        Validate a video file.

        Args:
            video_file: Video file object
            max_size_mb (int): Maximum file size in MB
            max_duration (int): Maximum duration in seconds
            allowed_formats (list): List of allowed formats

        Returns:
            bool: True if valid, False otherwise

        Raises:
            MediaProcessingException: If validation fails
        """
        try:
            # Check format
            if hasattr(video_file, "name"):
                file_ext = (
                    os.path.splitext(os.path.basename(video_file.name))[1]
                    .lower()
                    .lstrip(".")
                )
                if allowed_formats and file_ext not in allowed_formats:
                    raise MediaProcessingException(
                        f"Video format '{file_ext}' not allowed. Allowed formats: {', '.join(allowed_formats)}"
                    )

            # Check file size
            if hasattr(video_file, "size"):
                size_mb = video_file.size / (1024 * 1024)
                if size_mb > max_size_mb:
                    raise MediaProcessingException(
                        f"Video size ({size_mb:.1f}MB) exceeds maximum ({max_size_mb}MB)"
                    )

            # Check if ffprobe is available for duration check
            if os.path.isfile(FFPROBE_PATH) and os.access(FFPROBE_PATH, os.X_OK):
                # Create temp file for ffprobe with a secure random name
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
                    # Write input file to temp file
                    for chunk in video_file.chunks():
                        tmp.write(chunk)
                    tmp.flush()

                    # Get video duration using absolute path to ffprobe
                    cmd = [
                        FFPROBE_PATH,
                        "-v",
                        "error",
                        "-show_entries",
                        "format=duration",
                        "-of",
                        "default=noprint_wrappers=1:nokey=1",
                        tmp.name,
                    ]
                    result = subprocess.run(
                        cmd, capture_output=True, text=True, check=True
                    )
                    duration = float(result.stdout.strip())

                    # Check duration
                    if duration > max_duration:
                        raise MediaProcessingException(
                            f"Video duration ({duration:.1f}s) exceeds maximum ({max_duration}s)"
                        )

                    # Clean up
                    os.unlink(tmp.name)
            else:
                logger.warning(
                    f"ffprobe not available at {FFPROBE_PATH}, skipping duration check"
                )

            # Seek to beginning of file for future processing
            if hasattr(video_file, "seek"):
                video_file.seek(0)

            return True

        except MediaProcessingException:
            # Re-raise known exceptions
            raise
        except Exception as e:
            logger.error(f"Error validating video: {e}")
            raise MediaProcessingException(f"Invalid video file: {e}")
