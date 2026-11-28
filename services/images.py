"""Fotos de produtos persistidas no MongoDB e servidas como WebP."""
from io import BytesIO
import re
from pathlib import Path
from uuid import uuid4

from flask import Blueprint, abort, current_app, send_file
from pymongo.errors import PyMongoError
from services.db import get_database
from PIL import Image, ImageOps, UnidentifiedImageError

bp = Blueprint("product_images", __name__)
IMAGE_PREFIX = "/midia/produtos/"
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
            output = BytesIO()
            img.save(output, format="WEBP", quality=85, method=4)
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError(f"Não foi possível processar a imagem: {exc}") from exc

    filename = uuid4().hex + ".webp"
    get_database()["imagens_produtos"].insert_one({"_id": filename, "webp": output.getvalue()})
    return IMAGE_PREFIX + filename


@bp.get(IMAGE_PREFIX + "<filename>")
def product_image(filename):
    if not re.fullmatch(r"[0-9a-f]{32}\.webp", filename):
        abort(404)
    try:
        photo = get_database()["imagens_produtos"].find_one({"_id": filename})
    except (PyMongoError, RuntimeError):
        abort(503)
    if not photo:
        abort(404)
    return send_file(BytesIO(photo["webp"]), mimetype="image/webp", etag=filename, max_age=86400)


def remove_product_image(image_url):
    if image_url and image_url.startswith(IMAGE_PREFIX):
        filename = image_url.removeprefix(IMAGE_PREFIX)
        try:
            get_database()["imagens_produtos"].delete_one({"_id": filename})
        except (PyMongoError, RuntimeError):
            current_app.logger.warning("Falha ao limpar foto antiga do catálogo.")
        return
    if not image_url or not image_url.startswith("/static/uploads/"):
        return
    filename = image_url.removeprefix("/static/uploads/")
    if filename.endswith(".webp") and Path(filename).name == filename:
        try:
            (Path(current_app.static_folder) / "uploads" / filename).unlink(missing_ok=True)
        except OSError:
            current_app.logger.warning("Falha ao limpar foto local antiga.")
