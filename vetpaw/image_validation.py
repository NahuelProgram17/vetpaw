"""Validaciones comunes para imágenes subidas por usuarios de VetPaw."""
from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from PIL import Image, UnidentifiedImageError
from rest_framework import serializers

ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_DIMENSION = 12_000
MIN_IMAGE_DIMENSION = 32


def validate_uploaded_image(upload, *, max_mb: int = 5, label: str = "La imagen"):
    """Valida peso, contenido real y dimensiones; devuelve el mismo archivo."""
    if not upload:
        return upload

    max_bytes = max_mb * 1024 * 1024
    size = getattr(upload, "size", 0) or 0
    if size > max_bytes:
        raise serializers.ValidationError(f"{label} no puede superar los {max_mb} MB.")

    content_type = (getattr(upload, "content_type", "") or "").lower()
    if content_type and content_type not in ALLOWED_IMAGE_MIME_TYPES:
        raise serializers.ValidationError(f"{label} debe ser JPG, PNG o WebP.")

    original_position = None
    try:
        if hasattr(upload, "tell"):
            original_position = upload.tell()
        if hasattr(upload, "seek"):
            upload.seek(0)

        with Image.open(upload) as image:
            image_format = (image.format or "").upper()
            width, height = image.size
            image.verify()

        if image_format not in ALLOWED_IMAGE_FORMATS:
            raise serializers.ValidationError(f"{label} debe ser JPG, PNG o WebP.")
        if min(width, height) < MIN_IMAGE_DIMENSION:
            raise serializers.ValidationError(f"{label} es demasiado pequeña.")
        if max(width, height) > MAX_IMAGE_DIMENSION:
            raise serializers.ValidationError(
                f"{label} es demasiado grande. El máximo es {MAX_IMAGE_DIMENSION}px por lado."
            )
    except serializers.ValidationError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError, DjangoValidationError):
        raise serializers.ValidationError(f"{label} no es un archivo de imagen válido.")
    finally:
        if hasattr(upload, "seek"):
            upload.seek(original_position or 0)

    return upload
