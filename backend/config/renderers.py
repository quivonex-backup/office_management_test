
from urllib.parse import urlparse, unquote

from django.conf import settings
from rest_framework.renderers import JSONRenderer


class S3JSONRenderer(JSONRenderer):

    def render(self, data, accepted_media_type=None,
               renderer_context=None):

        if not getattr(settings, "S3_RETURN_FULL_URL", True):
            data = self.convert_s3_urls(data)

        return super().render(
            data, accepted_media_type, renderer_context
        )

    def convert_s3_urls(self, value):

        if isinstance(value, dict):
            return {
                key: self.convert_s3_urls(item)
                for key, item in value.items()
            }

        if isinstance(value, list):
            return [
                self.convert_s3_urls(item)
                for item in value
            ]

        if isinstance(value, str):
            parsed = urlparse(value)

            bucket = settings.AWS_STORAGE_BUCKET_NAME
            region = settings.AWS_S3_REGION_NAME

            allowed_hosts = {
                f"{bucket}.s3.amazonaws.com",
                f"{bucket}.s3.{region}.amazonaws.com",
            }

            if (
                parsed.scheme == "https"
                and parsed.hostname in allowed_hosts
            ):
                return unquote(parsed.path.lstrip("/"))

        return value
