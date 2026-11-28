"""Testes sem conexão externa para fotos e ordem do carrossel."""
from datetime import datetime, timezone

import mongomock
from services.product_photos import curated_photo, visible_photo
from services.products import list_products, serialize_product
from aplicar_fotos_produtos import update_photos


def test_demo_photo_matches_name_and_category():
    assert curated_photo('Sofá retrátil e reclinável 3 lugares', 'Sofás') == '/static/img/produtos/sofa-retratil-3-lugares.webp'
    assert curated_photo('Sofa RETRATIL E RECLINAVEL 3 lugares', 'sofas') is not None
    assert curated_photo('Sofá retrátil e reclinável 3 lugares', 'Fogões') is None


def test_default_svg_replaced_on_display_but_custom_kept():
    example = dict(_id='id1', nome='Geladeira duplex inox', categoria='Geladeiras', imagem='/static/img/geladeira.svg')
    assert serialize_product(example)['imagem'] == '/static/img/produtos/geladeira-duplex-inox.webp'
    example['imagem'] = '/static/uploads/minha-foto.webp'
    assert serialize_product(example)['imagem'] == '/static/uploads/minha-foto.webp'


def test_migration_preserves_prices_and_custom_images():
    col = mongomock.MongoClient().db.produtos
    col.insert_many([
        dict(nome='Geladeira duplex inox', categoria='Geladeiras', imagem='/static/img/geladeira.svg', preco_centavos=199990, estoque=3),
        dict(nome='Cama casal com cabeceira estofada', categoria='Camas', imagem='/static/uploads/custom.webp', preco_centavos=99990, estoque=1),
    ])
    updated, skipped, _ = update_photos(col)
    assert (updated, skipped) == (1, 1)
    geladeira = col.find_one({'categoria': 'Geladeiras'})
    assert geladeira['imagem'] == '/static/img/produtos/geladeira-duplex-inox.webp'
    assert geladeira['preco_centavos'] == 199990 and geladeira['estoque'] == 3
    assert col.find_one({'categoria': 'Camas'})['imagem'] == '/static/uploads/custom.webp'
    updated2, _, _ = update_photos(col)
    assert updated2 == 0


def test_carousel_shows_eight_featured_photos(monkeypatch):
    from services.product_photos import PHOTOS
    col = mongomock.MongoClient().db.produtos
    monkeypatch.setattr("services.products.collection", lambda: col)
    for name, category, _, _ in PHOTOS:
        col.insert_one(dict(nome=name, categoria=category, estoque=2, ativo=True,
                            destaque=True, criado_em=datetime.now(timezone.utc)))
    col.insert_one(dict(nome="Outro produto", categoria="Outros", estoque=9, ativo=True,
                        destaque=False, criado_em=datetime.now(timezone.utc)))
    result = list_products(featured_in_stock=True, limit=8)
    assert len(result) == 8
    assert all(curated_photo(item["nome"], item["categoria"]) for item in result)
