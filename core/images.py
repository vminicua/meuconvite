from __future__ import annotations

from io import BytesIO
from pathlib import Path

from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image, ImageOps


def normalise_gallery_image(upload) -> InMemoryUploadedFile:
    """Return a browser-safe, correctly oriented JPEG for a gallery upload."""
    upload.seek(0)
    with Image.open(upload) as source:
        image = ImageOps.exif_transpose(source)
        # HEIC/AVIF may contain transparency. Compose it over white instead of
        # letting JPEG turn transparent pixels black.
        if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
            rgba = image.convert("RGBA")
            background = Image.new("RGB", rgba.size, "white")
            background.paste(rgba, mask=rgba.getchannel("A"))
            image = background
        else:
            image = image.convert("RGB")

        output = BytesIO()
        image.save(output, format="JPEG", quality=90, optimize=True)

    output.seek(0)
    filename = f"{Path(upload.name).stem}.jpg"
    return InMemoryUploadedFile(
        output,
        field_name=getattr(upload, "field_name", "photos"),
        name=filename,
        content_type="image/jpeg",
        size=output.getbuffer().nbytes,
        charset=None,
    )
