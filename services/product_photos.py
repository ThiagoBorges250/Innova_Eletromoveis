"""Fotos reais fornecidas para os oito produtos de demonstração da Innova.

O mapeamento usa nome + categoria (normalizados) para não atribuir
uma foto a outro item e não sobrescreve imagens personalizadas.
"""
import re
import unicodedata


def _normalize(text):
    text = unicodedata.normalize("NFKD", str(text or "")).casefold()
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


# Nome, categoria, URL de foto, URL antiga de ilustração.
PHOTOS = [
    ('Sofá retrátil e reclinável 3 lugares', 'Sofás', '/static/img/produtos/sofa-retratil-3-lugares.webp', '/static/img/sofa.svg'),
    ('Cama casal com cabeceira estofada', 'Camas', '/static/img/produtos/cama-casal-estofada.webp', '/static/img/cama.svg'),
    ('Guarda-roupas 6 portas amadeirado', 'Guarda-roupas', '/static/img/produtos/guarda-roupas-6-portas.webp', '/static/img/armario.svg'),
    ('Mesa de jantar com 4 cadeiras', 'Salas de jantar', '/static/img/produtos/mesa-jantar-4-cadeiras.webp', '/static/img/jantar.svg'),
    ('Rack para TV e painel moderno', 'Racks e painéis', '/static/img/produtos/rack-tv-painel.webp', '/static/img/rack.svg'),
    ('Geladeira duplex inox', 'Geladeiras', '/static/img/produtos/geladeira-duplex-inox.webp', '/static/img/geladeira.svg'),
    ('Fogão 4 bocas com forno', 'Fogões', '/static/img/produtos/fogao-4-bocas.webp', '/static/img/fogao.svg'),
    ('Máquina de lavar 12 kg', 'Máquinas de lavar', '/static/img/produtos/maquina-lavar-12kg.webp', '/static/img/lavadora.svg'),
]

_MAP = {(_normalize(name), _normalize(cat)): (photo, legacy)
        for name, cat, photo, legacy in PHOTOS}


def curated_photo(name, category):
    """Foto apropriada a um item do conjunto de demonstração; ou None."""
    match = _MAP.get((_normalize(name), _normalize(category)))
    return match[0] if match else None


def visible_photo(name, category, stored_image):
    """Exibe foto real quando a imagem no Mongo é a ilustração antiga.

    Mantém imagens personalizadas do painel admin. Para gravar as URLs novas
    permanentemente no Mongo, execute aplicar_fotos_produtos.py.
    """
    match = _MAP.get((_normalize(name), _normalize(category)))
    if not match:
        return stored_image or '/static/img/sem-foto.svg'
    photo, legacy = match
    if not stored_image or stored_image in (legacy, '/static/img/sem-foto.svg'):
        return photo
    return stored_image
