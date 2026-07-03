import os

from django.utils.deconstruct import deconstructible

from cloudinary_storage.storage import MediaCloudinaryStorage, RESOURCE_TYPES


@deconstructible
class ClinicalFileCloudinaryStorage(MediaCloudinaryStorage):
    """Cloudinary storage mixto para archivos clínicos.

    - Imágenes: se suben como image/upload para tener preview normal.
    - PDFs: se suben como raw/upload para que Chrome los abra como PDF real.
    """

    def _get_resource_type(self, name):
        ext = os.path.splitext(str(name or ""))[1].lower()
        if ext == ".pdf":
            return RESOURCE_TYPES["RAW"]
        return RESOURCE_TYPES["IMAGE"]
