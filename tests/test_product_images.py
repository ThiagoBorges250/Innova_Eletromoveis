from io import BytesIO

import mongomock
from PIL import Image
from werkzeug.datastructures import FileStorage


def test_uploaded_photo_survives_app_restart(monkeypatch):
    from app import create_app
    from services.images import remove_product_image, save_product_image

    database = mongomock.MongoClient().db
    monkeypatch.setattr("services.images.get_database", lambda: database)
    source = BytesIO()
    Image.new("RGB", (32, 18), "white").save(source, "PNG")
    source.seek(0)
    with create_app().app_context():
        url = save_product_image(FileStorage(stream=source, filename="televisao.png"))
    second_app = create_app()
    client = second_app.test_client()
    response = client.get(url)
    assert response.status_code == 200
    assert response.mimetype == "image/webp"
    assert Image.open(BytesIO(response.data)).size == (32, 18)
    with second_app.app_context():
        remove_product_image(url)
    assert client.get(url).status_code == 404
