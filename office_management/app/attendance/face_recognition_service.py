
import logging
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

from django.core.exceptions import ObjectDoesNotExist


logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).resolve().parent / "models"

DETECTOR_MODEL = MODEL_DIR / "face_detection_yunet_2023mar.onnx"
RECOGNIZER_MODEL = MODEL_DIR / "face_recognition_sface_2021dec.onnx"

# OpenCV's documented SFace cosine similarity threshold.
# Test with your own camera images before production use.
COSINE_THRESHOLD = 0.363

MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGE_DIMENSION = 1280


class FaceVerificationError(Exception):
    """Safe, user-facing face verification error."""


def _check_model_files():
    for model_path in (DETECTOR_MODEL, RECOGNIZER_MODEL):
        if not model_path.is_file():
            raise FaceVerificationError(
                f"Face recognition model is missing: {model_path.name}. "
                "Install the required model files and restart the server."
            )

        if model_path.stat().st_size < 100_000:
            raise FaceVerificationError(
                f"Face recognition model is incomplete: {model_path.name}."
            )


@lru_cache(maxsize=1)
def _get_models():
    """Initialize the detector and recognizer once per process."""
    _check_model_files()

    try:
        detector = cv2.FaceDetectorYN.create(
            str(DETECTOR_MODEL),
            "",
            (320, 320),
            0.8,
            0.3,
            5000,
        )

        recognizer = cv2.FaceRecognizerSF.create(
            str(RECOGNIZER_MODEL),
            "",
        )

        # Use CPU inference for compatibility and predictable setup.
        return detector, recognizer

    except Exception as exc:
        logger.exception("Could not initialize OpenCV face models")
        raise FaceVerificationError(
            "Face recognition models could not be initialized. "
            "Check the OpenCV installation and model files."
        ) from exc


def _read_uploaded_image(uploaded_file):
    if not uploaded_file:
        raise FaceVerificationError("A selfie image is required.")

    if getattr(uploaded_file, "size", 0) > MAX_IMAGE_BYTES:
        raise FaceVerificationError(
            "Image is too large. Upload an image smaller than 8 MB."
        )

    try:
        uploaded_file.seek(0)
        image_bytes = uploaded_file.read(MAX_IMAGE_BYTES + 1)
        uploaded_file.seek(0)
    except Exception as exc:
        raise FaceVerificationError(
            "Unable to read the submitted image."
        ) from exc

    if not image_bytes or len(image_bytes) > MAX_IMAGE_BYTES:
        raise FaceVerificationError(
            "The image is empty or exceeds the 8 MB limit."
        )

    image_array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

    if image is None:
        raise FaceVerificationError(
            "The uploaded file is not a supported image."
        )

    height, width = image.shape[:2]
    largest_dimension = max(height, width)

    if largest_dimension > MAX_IMAGE_DIMENSION:
        scale = MAX_IMAGE_DIMENSION / largest_dimension
        new_width = max(1, int(width * scale))
        new_height = max(1, int(height * scale))

        image = cv2.resize(
            image,
            (new_width, new_height),
            interpolation=cv2.INTER_AREA,
        )

    return image


def _detect_single_face(image):
    detector, recognizer = _get_models()

    height, width = image.shape[:2]
    detector.setInputSize((width, height))

    _, faces = detector.detect(image)

    if faces is None or len(faces) == 0:
        raise FaceVerificationError(
            "No face detected. Look at the camera with your face clearly visible."
        )

    if len(faces) != 1:
        raise FaceVerificationError(
            "Please submit an image containing exactly one visible face."
        )

    try:
        aligned_face = recognizer.alignCrop(image, faces[0])
        embedding = recognizer.feature(aligned_face)

        if embedding is None or embedding.size == 0:
            raise ValueError("Empty face embedding")

        return embedding

    except FaceVerificationError:
        raise
    except Exception as exc:
        logger.exception("Failed to extract face representation")
        raise FaceVerificationError(
            "Could not process the detected face. Try a clearer image."
        ) from exc


@lru_cache(maxsize=512)
def _get_registered_embedding(
    employee_id,
    photo_name,
    updated_at_key,
):
    """
    Cache the registered face embedding.

    The photo filename and updated timestamp are part of the cache key.
    A change to either will generate a new cached entry.
    """
    # Import locally to avoid model-import circular dependencies.
    from app.employees.models import Employee

    try:
        employee = Employee.objects.get(pk=employee_id)

        if (
            not employee.profile_photo
            or employee.profile_photo.name != photo_name
        ):
            raise FaceVerificationError(
                "The employee's registered profile photo has changed. "
                "Please retry verification."
            )

        with employee.profile_photo.open("rb") as image_file:
            image_bytes = image_file.read(MAX_IMAGE_BYTES + 1)

    except FaceVerificationError:
        raise
    except ObjectDoesNotExist as exc:
        raise FaceVerificationError(
            "Employee profile was not found."
        ) from exc
    except Exception as exc:
        logger.exception(
            "Could not read registered photo for employee_id=%s",
            employee_id,
        )
        raise FaceVerificationError(
            "Could not read the registered profile photo."
        ) from exc

    if not image_bytes or len(image_bytes) > MAX_IMAGE_BYTES:
        raise FaceVerificationError(
            "Registered profile photo is empty or too large."
        )

    image_array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

    if image is None:
        raise FaceVerificationError(
            "Registered profile photo is not a valid image."
        )

    height, width = image.shape[:2]
    largest_dimension = max(height, width)

    if largest_dimension > MAX_IMAGE_DIMENSION:
        scale = MAX_IMAGE_DIMENSION / largest_dimension
        image = cv2.resize(
            image,
            (
                max(1, int(width * scale)),
                max(1, int(height * scale)),
            ),
            interpolation=cv2.INTER_AREA,
        )

    return _detect_single_face(image)


def verify_employee_face(employee, selfie_file):
    """
    Compare the employee's registered profile photo with the selfie.

    Uses the face_match_threshold configured for the employee's
    organization. Does not create or update attendance records.
    """
    if not employee.profile_photo:
        raise FaceVerificationError(
            "No registered profile photo exists for this employee."
        )

    if not selfie_file:
        raise FaceVerificationError("A selfie image is required.")

    if not employee.organization_id:
        raise FaceVerificationError(
            "The employee is not linked to an organization."
        )

    try:
        # Import here to avoid unnecessary model-import dependencies.
        from app.attendance.models import AttendanceSettings

        attendance_settings, _ = (
            AttendanceSettings.objects.get_or_create(
                organization_id=employee.organization_id
            )
        )

        # The organization setting is on a 0-100 scale.
        # Convert it to the cosine similarity scale used by SFace.
        threshold_percent = float(
            attendance_settings.face_match_threshold
        )
        threshold_cosine = threshold_percent / 100.0

        selfie_image = _read_uploaded_image(selfie_file)

        updated_at_key = (
            employee.updated_at.isoformat()
            if employee.updated_at
            else ""
        )

        registered_embedding = _get_registered_embedding(
            employee.pk,
            employee.profile_photo.name,
            updated_at_key,
        )

        selfie_embedding = _detect_single_face(selfie_image)

        _, recognizer = _get_models()

        cosine_score = float(
            recognizer.match(
                registered_embedding,
                selfie_embedding,
                cv2.FaceRecognizerSF_FR_COSINE,
            )
        )

        verified = cosine_score >= threshold_cosine

        return {
            "verified": verified,
            "similarity": cosine_score,
            "threshold": threshold_cosine,
            "threshold_percent": threshold_percent,
        }

    except FaceVerificationError:
        raise

    except Exception as exc:
        logger.exception(
            "Unexpected face verification error for employee_id=%s",
            employee.pk,
        )
        raise FaceVerificationError(
            "Face verification failed. Check the server logs."
        ) from exc
