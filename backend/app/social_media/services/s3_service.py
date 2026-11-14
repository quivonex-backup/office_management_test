import os
import uuid
import logging
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)


def generate_unique_filename(file_name):
    """
    Generate a unique filename while preserving the original file extension.

    Example:
        photo.jpg -> 9d8cfe70a4d04f289c11c24534e3a922.jpg
    """
    if not file_name:
        return None
    extension = os.path.splitext(file_name)[1].lower()
    return f"{uuid.uuid4().hex}{extension}"


def upload_to_s3(file, folder):
    """
    Upload a file to the configured Django storage backend (e.g., S3).

    Args:
        file: Django UploadedFile object.
        folder: S3 folder/object prefix (e.g., 'users/profile').

    Returns:
        Saved object path (e.g., 'users/profile/abc123.jpg'), or None if no file.

    Raises:
        ValueError if folder is empty.
        Exception if upload fails.
    """
    if not file:
        return None
    if not folder:
        raise ValueError("S3 folder is required.")

    try:
        unique_filename = generate_unique_filename(file.name)
        folder = folder.strip("/")
        file_path = f"{folder}/{unique_filename}"
        saved_path = default_storage.save(file_path, file)
        return saved_path
    except Exception as exc:
        logger.exception("S3 file upload failed. Folder: %s", folder)
        raise exc


def delete_from_s3(file_path):
    """
    Delete a file from the configured storage backend.

    Args:
        file_path: Stored object path (e.g., 'users/profile/abc.jpg')
                   or a FieldFile instance.

    Returns:
        True if deleted or file does not exist; False if no path provided.

    Raises:
        Exception if storage deletion fails.
    """
    if not file_path:
        return False

    try:
        # Handle FieldFile or string
        if hasattr(file_path, "name"):
            file_path = file_path.name
        file_path = str(file_path).strip()
        if not file_path:
            return False

        if default_storage.exists(file_path):
            default_storage.delete(file_path)
        return True
    except Exception as exc:
        logger.exception("S3 file deletion failed. Path: %s", file_path)
        raise exc


def update_s3_file(new_file, old_file_path, folder):
    """
    Replace an existing S3 file with a new one.

    Process:
        1. Upload new file.
        2. Confirm upload succeeded.
        3. Delete old file (if different from new).
        4. Return new file path.

    Args:
        new_file: New Django UploadedFile.
        old_file_path: Existing object path or FieldFile.
        folder: Folder for the new file.

    Returns:
        New stored file path; if no new file provided, returns old_file_path.
    """
    if not new_file:
        return old_file_path.name if hasattr(old_file_path, "name") else old_file_path

    # Upload new file first
    new_file_path = upload_to_s3(file=new_file, folder=folder)

    # Delete old file after successful upload
    if old_file_path:
        old_path = old_file_path.name if hasattr(old_file_path, "name") else old_file_path
        if old_path and old_path != new_file_path:
            delete_from_s3(old_path)

    return new_file_path