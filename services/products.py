"""Persistência de produtos no MongoDB — preços em centavos, sem imprecisão de float."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ASCENDING, DESCENDING

from services.db import get_database
from services.product_photos import visible_photo

CATEGORIES = [
    "Sofás", "Camas", "Guarda-roupas", "Salas de jantar",
    "Racks e painéis", "Geladeiras", "Fogões", "Máquinas de lavar", "Outros",
]


def format_brl(cents):
    """Formata um inteiro de centavos como moeda brasileira."""
    cents = int(cents or 0)
    number = f"{abs(cents) // 100:,}".replace(",", ".")
    sign = "-" if cents < 0 else ""
    return f"{sign}R$ {number},{abs(cents) % 100:02d}"


def parse_price(value):
    """Aceita '1899,90', '1.899,90' ou '1899.90'."""
    clean = str(value or "").strip().replace("R$", "").replace(" ", "")
    if not clean or any(c not in "0123456789,." for c in clean):
        raise ValueError("Preço inválido.")
    if "," in clean:
        clean = clean.replace(".", "").replace(",", ".")
    elif clean.count(".") > 1:
        clean = clean.replace(".", "")
    try:
        value_dec = Decimal(clean)
    except InvalidOperation as exc:
        raise ValueError("Preço inválido.") from exc
    if not value_dec.is_finite() or value_dec <= 0 or value_dec > Decimal("10000000"):
        raise ValueError("Informe um preço maior que zero e inferior a R$ 10 milhões.")
    return int((value_dec * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _oid(value):
    try:
        return ObjectId(str(value))
    except (InvalidId, TypeError):
        return None


def serialize_product(doc):
    if not doc:
        return None
    data = dict(doc)
    data["id"] = str(data.pop("_id"))
    data["preco_centavos"] = int(data.get("preco_centavos", 0))
    data["imagem"] = visible_photo(data.get("nome"), data.get("categoria"), data.get("imagem"))
    return data


def collection():
    return get_database()["produtos"]


def ensure_indexes():
    col = collection()
    col.create_index([("ativo", ASCENDING), ("criado_em", DESCENDING)])
    col.create_index([("categoria", ASCENDING), ("nome", ASCENDING)])


def list_products(*, category=None, search=None, admin=False, limit=60):
    query = {} if admin else {"ativo": True}
    if category and category in CATEGORIES:
        query["categoria"] = category
    if search:
        # Escapa caracteres de regex do usuário e limita tamanho da consulta.
        import re
        query["nome"] = {"$regex": re.escape(search[:80]), "$options": "i"}
    docs = collection().find(query).sort("criado_em", DESCENDING).limit(limit)
    return [serialize_product(doc) for doc in docs]


def get_product(product_id, *, admin=False):
    oid = _oid(product_id)
    if oid is None:
        return None
    query = {"_id": oid}
    if not admin:
        query["ativo"] = True
    return serialize_product(collection().find_one(query))


def get_products_by_ids(ids, *, admin=False):
    valid = [_oid(pid) for pid in ids]
    valid = [oid for oid in valid if oid is not None]
    if not valid:
        return {}
    query = {"_id": {"$in": valid}}
    if not admin:
        query["ativo"] = True
    return {str(doc["_id"]): serialize_product(doc) for doc in collection().find(query)}


def validate_product_form(form):
    nome = (form.get("nome") or "").strip()
    descricao = (form.get("descricao") or "").strip()
    categoria = (form.get("categoria") or "").strip()
    if not (3 <= len(nome) <= 120):
        raise ValueError("O nome precisa ter entre 3 e 120 caracteres.")
    if categoria not in CATEGORIES:
        raise ValueError("Selecione uma categoria válida.")
    if len(descricao) > 2000:
        raise ValueError("A descrição pode ter até 2.000 caracteres.")
    try:
        estoque = int(form.get("estoque") or "0")
    except ValueError as exc:
        raise ValueError("Estoque inválido.") from exc
    if not (0 <= estoque <= 100000):
        raise ValueError("O estoque precisa estar entre 0 e 100.000.")
    return {
        "nome": nome,
        "descricao": descricao,
        "categoria": categoria,
        "preco_centavos": parse_price(form.get("preco")),
        "estoque": estoque,
        "destaque": form.get("destaque") == "on",
        "ativo": form.get("ativo") == "on",
        "atualizado_em": datetime.now(timezone.utc),
    }


def create_product(data):
    now = datetime.now(timezone.utc)
    data = dict(data)
    data["criado_em"] = now
    return str(collection().insert_one(data).inserted_id)


def update_product(product_id, data):
    oid = _oid(product_id)
    return bool(oid and collection().update_one({"_id": oid}, {"$set": dict(data)}).matched_count)


def delete_product(product_id):
    oid = _oid(product_id)
    return bool(oid and collection().delete_one({"_id": oid}).deleted_count)
