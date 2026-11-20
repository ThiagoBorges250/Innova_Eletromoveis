"""Upload local seguro: valida a imagem e converte para WebP."""
from pathlib import Path
from uuid import uuid4

from flask import current_app
from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


def save_product_image(file):
    if not file or not file.filename:
        return None
    try:
        # A imagem é reprocessada (não preservamos metadados/EXIF nem nome fornecido).
        with Image.open(file.stream) as original:
            if original.format not in ALLOWED_FORMATS:
                raise ValueError("Envie uma imagem JPG, PNG ou WebP.")
            if original.width * original.height > 25_000_000:
                raise ValueError("A resolução da imagem é muito grande.")
            img = ImageOps.exif_transpose(original).convert("RGB")
            img.thumbnail((1400, 1400))
            folder = Path(current_app.static_folder) / "uploads"
            folder.mkdir(parents=True, exist_ok=True)
            filename = uuid4().hex + ".webp"
            img.save(folder / filename, format="WEBP", quality=85, method=4)
            return "/static/uploads/" + filename
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError(f"Não foi possível processar a imagem: {exc}") from exc


def remove_product_image(image_url):
    if not image_url or not image_url.startswith("/static/uploads/"):
        return
    filename = image_url.removeprefix("/static/uploads/")
    if filename.endswith(".webp") and Path(filename).name == filename:
        (Path(current_app.static_folder) / "uploads" / filename).unlink(missing_ok=True)
