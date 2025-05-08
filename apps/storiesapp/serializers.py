from rest_framework import serializers

from apps.shopapp.serializers import ShopMinimalSerializer
from apps.storiesapp.models import Story, StoryView


class StorySerializer(serializers.ModelSerializer):
    """
    Full serializer for Story model, including shop details and view statistics
    """

    shop = ShopMinimalSerializer(read_only=True)
    shop_id = serializers.UUIDField(write_only=True)
    time_left = serializers.SerializerMethodField()
    view_count = serializers.SerializerMethodField()
    has_viewed = serializers.SerializerMethodField()

    class Meta:
        model = Story
        fields = [
            "id",
            "shop",
            "shop_id",
            "story_type",
            "media_url",
            "thumbnail_url",
            "created_at",
            "expires_at",
            "is_active",
            "time_left",
            "view_count",
            "has_viewed",
        ]
        read_only_fields = ["created_at", "expires_at", "is_active"]

    def get_time_left(self, obj):
        """Get time left before expiry in seconds"""
        return obj.time_left

    def get_view_count(self, obj):
        """Get number of views"""
        return obj.view_count

    def get_has_viewed(self, obj):
        """Check if current user has viewed this story"""
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            customer = request.user
            return StoryView.objects.filter(story=obj, customer=customer).exists()
        return False

    def validate(self, data):
        """
        Validate that the shop exists and that the media URL is appropriate
        for the story type selected
        """
        story_type = data.get("story_type")
        media_url = data.get("media_url")

        # Validate media URL matches story type
        if story_type == "image":
            valid_extensions = [".jpg", ".jpeg", ".png", ".gif", ".webp"]
        else:  # video
            valid_extensions = [".mp4", ".mov", ".avi", ".webm"]

        # Simple check for file extension
        is_valid = any(media_url.lower().endswith(ext) for ext in valid_extensions)
        if not is_valid:
            raise serializers.ValidationError(
                {
                    "media_url": f"Media URL does not appear to be a valid {story_type} file"
                }
            )

        return data


class StoryCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new stories. Accepts file uploads which are then
    processed and stored in S3 before creating the Story record.
    """

    media_file = serializers.FileField(write_only=True)
    shop_id = serializers.UUIDField()

    class Meta:
        model = Story
        fields = ["id", "shop_id", "story_type", "media_file"]

    def validate_story_type(self, value):
        """Ensure story type is either image or video"""
        if value not in ["image", "video"]:
            raise serializers.ValidationError(
                "Story type must be either 'image' or 'video'"
            )
        return value

    def create(self, validated_data):
        """
        Create story by processing the uploaded file first, then storing the record
        """
        from apps.storiesapp.services.media_service import StoryMediaService

        media_file = validated_data.pop("media_file")
        shop_id = validated_data.pop("shop_id")
        story_type = validated_data.get("story_type")

        # Process media file
        media_service = StoryMediaService()
        result = media_service.process_story_media(media_file, story_type, shop_id)

        # Create story record
        story = Story.objects.create(
            shop_id=shop_id,
            story_type=story_type,
            media_url=result["media_url"],
            thumbnail_url=result.get("thumbnail_url"),
        )

        return story


class StoryViewSerializer(serializers.ModelSerializer):
    """
    Serializer for recording story views
    """

    class Meta:
        model = StoryView
        fields = ["id", "story", "customer", "viewed_at"]
        read_only_fields = ["viewed_at"]


class StoryMinimalSerializer(serializers.ModelSerializer):
    """
    Minimal version of story serializer for including in other responses
    """

    time_left = serializers.SerializerMethodField()
    has_viewed = serializers.SerializerMethodField()

    class Meta:
        model = Story
        fields = [
            "id",
            "story_type",
            "media_url",
            "thumbnail_url",
            "created_at",
            "time_left",
            "has_viewed",
        ]

    def get_time_left(self, obj):
        return obj.time_left

    def get_has_viewed(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            customer = request.user
            return StoryView.objects.filter(story=obj, customer=customer).exists()
        return False
