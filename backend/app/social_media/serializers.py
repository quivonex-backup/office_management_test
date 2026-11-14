from rest_framework import serializers

from .models import (
    SocialAccount,
    SocialPost,
    SocialPostMedia,
    SocialPublication,
)


# SOCIAL ACCOUNT SERIALIZER
class SocialAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialAccount
        fields = "__all__"
        read_only_fields = (
            "id",
            "access_token",
            "created_by",
            "created_at",
            "updated_at",
        )


# SOCIAL ACCOUNT MEDIA LIST
class SocialAccountMediaListSerializer(serializers.Serializer):
    account_id = serializers.IntegerField(required=True)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=100, default=25)
    after = serializers.CharField(required=False, allow_blank=False, allow_null=True)
    before = serializers.CharField(required=False, allow_blank=False, allow_null=True)

    def validate(self, attrs):
        if attrs.get("after") and attrs.get("before"):
            raise serializers.ValidationError("Use either 'after' or 'before', not both.")
        return attrs


# SOCIAL POST MEDIA SERIALIZER
class SocialPostMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialPostMedia
        fields = [
            "id",
            "media_type",
            "file",
            "sort_order",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
        ]


# SOCIAL POST SERIALIZER
class SocialPostSerializer(serializers.ModelSerializer):
    media = SocialPostMediaSerializer(
        many=True,
        read_only=True,
    )
    publications = serializers.SerializerMethodField()

    class Meta:
        model = SocialPost
        fields = "__all__"
        read_only_fields = (
            "id",
            "status",
            "created_by",
            "created_at",
            "updated_at",
            "media",
            "publications",
        )

    def get_publications(self, obj):
        publications = obj.publications.all()
        return SocialPublicationSerializer(
            publications,
            many=True,
        ).data


# SOCIAL POST ACTION SERIALIZER
class SocialPostActionSerializer(serializers.Serializer):
    post_id = serializers.IntegerField(required=True)

    def validate_post_id(self, value):
        if not SocialPost.objects.filter(id=value).exists():
            raise serializers.ValidationError(
                "Social post does not exist."
            )
        return value


# SOCIAL POST LIST SERIALIZER
class SocialPostListSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=SocialPost.STATUS_CHOICES,
        required=False,
        allow_blank=False,
    )
    page = serializers.IntegerField(
        required=False,
        min_value=1,
        default=1,
    )
    page_size = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=100,
        default=10,
    )


# SOCIAL ACCOUNT LIST SERIALIZER
class SocialAccountListSerializer(serializers.Serializer):
    platform = serializers.ChoiceField(
        choices=SocialAccount.PLATFORM_CHOICES,
        required=False,
    )
    is_active = serializers.BooleanField(required=False)


# SOCIAL ACCOUNT ACTION SERIALIZER
class SocialAccountActionSerializer(serializers.Serializer):
    account_id = serializers.IntegerField(required=True)

    def validate_account_id(self, value):
        if not SocialAccount.objects.filter(id=value).exists():
            raise serializers.ValidationError(
                "Social account does not exist."
            )
        return value


# SOCIAL PUBLISH SERIALIZER
class SocialPublishSerializer(serializers.Serializer):
    post_id = serializers.IntegerField(required=True)
    platforms = serializers.ListField(
        child=serializers.ChoiceField(
            choices=[
                ("FACEBOOK", "Facebook"),
                ("INSTAGRAM", "Instagram"),
            ]
        ),
        required=True,
        allow_empty=False,
    )

    def validate_post_id(self, value):
        if not SocialPost.objects.filter(id=value).exists():
            raise serializers.ValidationError(
                "Social post does not exist."
            )
        return value

    def validate_platforms(self, value):
        # Remove duplicates while preserving order.
        unique_platforms = list(dict.fromkeys(value))
        return unique_platforms


# SOCIAL SCHEDULE SERIALIZER
class SocialScheduleSerializer(serializers.Serializer):
    post_id = serializers.IntegerField(required=True)

    scheduled_at = serializers.DateTimeField(required=True)

    platforms = serializers.ListField(
        child=serializers.ChoiceField(
            choices=[
                ("FACEBOOK", "Facebook"),
                ("INSTAGRAM", "Instagram"),
            ]
        ),
        required=True,
        allow_empty=False,
    )

    def validate_post_id(self, value):
        request = self.context.get("request")

        try:
            post = SocialPost.objects.get(
                id=value,
                created_by=request.user,
            )
        except SocialPost.DoesNotExist:
            raise serializers.ValidationError(
                "Social post does not exist."
            )

        if post.status == "PUBLISHED":
            raise serializers.ValidationError(
                "Published post cannot be scheduled."
            )

        return value

    def validate_scheduled_at(self, value):
        from django.utils import timezone

        if value <= timezone.now():
            raise serializers.ValidationError(
                "Scheduled time must be in the future."
            )

        return value

    def validate_platforms(self, value):
        return list(dict.fromkeys(value))


# SOCIAL PUBLICATION SERIALIZER
class SocialPublicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialPublication
        fields = "__all__"
        read_only_fields = (
            "id",
            "post",
            "status",
            "platform_post_id",
            "platform_post_url",
            "error_message",
            "published_at",
            "created_at",
            "updated_at",
        )


# SOCIAL PUBLICATION ACTION SERIALIZER
class SocialPublicationActionSerializer(serializers.Serializer):
    publication_id = serializers.IntegerField(required=True)

    def validate_publication_id(self, value):
        if not SocialPublication.objects.filter(id=value).exists():
            raise serializers.ValidationError(
                "Publication does not exist."
            )
        return value