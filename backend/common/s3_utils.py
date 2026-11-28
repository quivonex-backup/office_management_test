
import os
import uuid
import logging
from urllib.parse import urlparse, unquote

from django.conf import settings
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)


def normalize_s3_path(file_path):
    """
    Convert a FieldFile, S3 URL, or object key
    into a storage object key.
    """
    if not file_path:
        return None

    if hasattr(file_path, "name"):
        file_path = file_path.name

    file_path = str(file_path).strip()

    if not file_path:
        return None

    parsed = urlparse(file_path)

    if parsed.scheme or parsed.netloc:
        if parsed.scheme != "https":
            raise ValueError("Invalid S3 URL")

        bucket = settings.AWS_STORAGE_BUCKET_NAME
        region = settings.AWS_S3_REGION_NAME

        allowed_hosts = {
            f"{bucket}.s3.amazonaws.com",
            f"{bucket}.s3.{region}.amazonaws.com",
        }

        if parsed.hostname not in allowed_hosts:
            raise ValueError("URL does not belong to configured S3 bucket")

        file_path = unquote(parsed.path.lstrip("/"))

    file_path = file_path.replace("\\", "/").lstrip("/")

    if not file_path or any(
        part in ("", ".", "..")
        for part in file_path.split("/")
    ):
        raise ValueError("Invalid S3 object key")

    return file_path


def generate_unique_filename(file_name):
    if not file_name:
        return None

    extension = os.path.splitext(file_name)[1].lower()
    return f"{uuid.uuid4().hex}{extension}"


def get_s3_file_url(file_path):
    """
    Return full S3 URL or object key according
    to the centralized setting.
    """
    key = normalize_s3_path(file_path)

    if not key:
        return None

    if settings.S3_RETURN_FULL_URL:
        return default_storage.url(key)

    return key


def upload_to_s3(file, folder):
    """
    Upload file and return its storage object key.
    """
    if not file:
        return None

    if not folder or not folder.strip("/"):
        raise ValueError("S3 folder is required")

    folder = folder.strip("/")
    filename = generate_unique_filename(file.name)
    file_path = f"{folder}/{filename}"

    try:
        return default_storage.save(file_path, file)

    except Exception:
        logger.exception(
            "S3 upload failed: %s", file_path
        )
        raise


def delete_from_s3(file_path):
    """
    Delete by object key, FieldFile, or S3 URL.

    Does not call HeadObject/exists().
    """
    key = normalize_s3_path(file_path)

    if not key:
        return False

    try:
        default_storage.delete(key)
        return True

    except Exception:
        logger.exception(
            "S3 deletion failed: %s", key
        )
        raise


def update_s3_file(new_file, old_file_path, folder):
    """
    Upload replacement first, then delete old file.

    Returns the new object key.
    """
    old_key = normalize_s3_path(old_file_path)

    if not new_file:
        return old_key

    new_key = upload_to_s3(new_file, folder)

    if old_key and old_key != new_key:
        delete_from_s3(old_key)

    return new_key
