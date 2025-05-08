from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.exceptions import APIException


class VideoProcessingError(APIException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = _("Error processing video file.")
    default_code = "video_processing_error"


class InvalidVideoFile(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _("The uploaded file is not a valid video file.")
    default_code = "invalid_video_file"


class VideoTooLarge(APIException):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    default_detail = _("The uploaded video file is too large.")
    default_code = "video_too_large"


class ReelAlreadyLiked(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _("You have already liked this reel.")
    default_code = "reel_already_liked"


class ReelAlreadyReported(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _("You have already reported this reel.")
    default_code = "reel_already_reported"


class InvalidReelStatus(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _("Invalid reel status transition.")
    default_code = "invalid_reel_status"


class ServiceRequiredForPublishing(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _(
        "At least one service or package must be linked before publishing."
    )
    default_code = "service_required"
