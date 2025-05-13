import ast
import os
import tempfile
import uuid

import ffmpeg

from core.storage.s3_storage import S3Storage

from ..exceptions import InvalidVideoFile, VideoProcessingError


class MediaService:
    """Service for processing media files (video, images) for reels"""

    @staticmethod
    def generate_thumbnail(video_path, output_path=None, timestamp=None):
        """
        Generate a thumbnail image from a video

        Args:
            video_path: Path to the video file
            output_path: Path where thumbnail should be saved (optional)
            timestamp: Time position for thumbnail in seconds (optional)

        Returns:
            Path to the generated thumbnail
        """
        try:
            # Get video info
            probe = ffmpeg.probe(video_path)
            video_info = next(
                (stream for stream in probe["streams"] if stream["codec_type"] == "video"),
                None,
            )

            if not video_info:
                raise InvalidVideoFile("No video stream found")

            # If timestamp not provided, use 1/3 of the duration
            if timestamp is None:
                duration = float(probe["format"]["duration"])
                timestamp = duration / 3

            # Generate temporary output path if not provided
            if output_path is None:
                handle, output_path = tempfile.mkstemp(suffix=".jpg")
                os.close(handle)

            # Extract frame using ffmpeg
            (
                ffmpeg.input(video_path, ss=timestamp)
                .filter("scale", 640, -1)  # Width 640px, maintain aspect ratio
                .output(output_path, vframes=1)
                .overwrite_output()
                .run(quiet=True)
            )

            return output_path
        except Exception as e:
            raise VideoProcessingError(f"Error generating thumbnail: {str(e)}")

    @staticmethod
    def optimize_video(video_path, output_path=None, target_size_mb=10, maintain_quality=True):
        """
        Optimize a video for web streaming

        Args:
            video_path: Path to the input video file
            output_path: Path where optimized video should be saved (optional)
            target_size_mb: Target file size in MB (optional)
            maintain_quality: Whether to prioritize quality over file size (optional)

        Returns:
            Path to the optimized video
        """
        try:
            # Generate temporary output path if not provided
            if output_path is None:
                handle, output_path = tempfile.mkstemp(suffix=".mp4")
                os.close(handle)

            # Get original video info
            probe = ffmpeg.probe(video_path)
            duration = float(probe["format"]["duration"])

            # Calculate target bitrate based on size goal
            target_size_bytes = target_size_mb * 1024 * 1024
            target_bitrate = int((target_size_bytes * 8) / duration)

            # Scale resolution based on original size
            video_stream = next(
                (stream for stream in probe["streams"] if stream["codec_type"] == "video"),
                None,
            )

            if not video_stream:
                raise InvalidVideoFile("No video stream found")

            # Get dimensions
            width = int(video_stream.get("width", 1280))
            height = int(video_stream.get("height", 720))

            # Determine target resolution
            if width > 1280 or height > 720:
                # Scale down to 720p max
                scale_filter = (
                    "scale=w=min(1280,iw):h=min(720,ih):force_original_aspect_ratio=decrease"
                )
            else:
                # Keep original resolution
                scale_filter = "scale=w=iw:h=ih"

            # Optimize video
            if maintain_quality:
                # CRF mode (18-28 is reasonable, lower is higher quality)
                crf = 23
                (
                    ffmpeg.input(video_path)
                    .filter(scale_filter)
                    .output(
                        output_path,
                        vcodec="libx264",
                        acodec="aac",
                        crf=crf,
                        preset="slow",
                        movflags="faststart",
                    )
                    .overwrite_output()
                    .run(quiet=True)
                )
            else:
                # Target bitrate mode
                (
                    ffmpeg.input(video_path)
                    .filter(scale_filter)
                    .output(
                        output_path,
                        vcodec="libx264",
                        acodec="aac",
                        b=f"{target_bitrate}",
                        maxrate=f"{int(target_bitrate * 1.5)}",
                        bufsize=f"{int(target_bitrate * 3)}",
                        preset="medium",
                        movflags="faststart",
                    )
                    .overwrite_output()
                    .run(quiet=True)
                )

            return output_path
        except Exception as e:
            raise VideoProcessingError(f"Error optimizing video: {str(e)}")

    @staticmethod
    def get_video_metadata(video_path):
        """
        Extract metadata from a video file

        Args:
            video_path: Path to the video file

        Returns:
            Dictionary with video metadata
        """
        try:
            # Get video info
            probe = ffmpeg.probe(video_path)

            # Extract relevant metadata
            metadata = {
                "format": probe["format"]["format_name"],
                "duration": float(probe["format"]["duration"]),
                "size": int(probe["format"]["size"]),
                "bit_rate": int(probe["format"].get("bit_rate", 0)),
                "streams": [],
            }

            # Extract stream information
            for stream in probe["streams"]:
                stream_type = stream.get("codec_type")

                if stream_type == "video":
                    metadata["streams"].append(
                        {
                            "type": "video",
                            "codec": stream.get("codec_name"),
                            "width": int(stream.get("width", 0)),
                            "height": int(stream.get("height", 0)),
                            "aspect_ratio": stream.get("display_aspect_ratio", ""),
                            "frame_rate": MediaService._safe_frame_rate_calc(
                                stream.get("avg_frame_rate", "0/1")
                            ),
                            "bit_rate": int(stream.get("bit_rate", 0)),
                        }
                    )
                elif stream_type == "audio":
                    metadata["streams"].append(
                        {
                            "type": "audio",
                            "codec": stream.get("codec_name"),
                            "channels": int(stream.get("channels", 0)),
                            "sample_rate": int(stream.get("sample_rate", 0)),
                            "bit_rate": int(stream.get("bit_rate", 0)),
                        }
                    )

            return metadata
        except Exception as e:
            raise VideoProcessingError(f"Error getting video metadata: {str(e)}")

    @staticmethod
    def upload_media_to_s3(file_path, prefix="reels"):
        """
        Upload a media file to S3

        Args:
            file_path: Path to the local file
            prefix: S3 path prefix

        Returns:
            S3 URL of the uploaded file
        """
        try:
            # Initialize S3 storage
            s3_storage = S3Storage()

            # Generate unique filename
            filename = os.path.basename(file_path)
            name, ext = os.path.splitext(filename)
            unique_filename = f"{prefix}/{uuid.uuid4()}{ext}"

            # Upload file
            with open(file_path, "rb") as f:
                s3_url = s3_storage.upload_file(f, unique_filename)

            return s3_url
        except Exception as e:
            raise Exception(f"Error uploading to S3: {str(e)}")

    @staticmethod
    def _safe_frame_rate_calc(frame_rate_str):
        """Safely calculate frame rate from string like '30000/1001' without using eval"""
        try:
            if not frame_rate_str or frame_rate_str == "0/1":
                return 0

            if "/" in frame_rate_str:
                numerator, denominator = frame_rate_str.split("/")
                return float(numerator) / float(denominator)
            else:
                return float(frame_rate_str)
        except (ValueError, ZeroDivisionError):
            return 0
