"""Reconciliação retomável do índice a partir do estado atual do MongoDB."""
import logging
import os
from contextlib import contextmanager

import httpx
from bson import ObjectId
from pymongo import timeout
from redis.exceptions import LockError

from services import embeddings, products, vector_store
from services.db import get_redis

BATCH_SIZE = 20
_PREFIX = "innova:ai:sync:"
logger = logging.getLogger(__name__)


class SyncBusy(RuntimeError):
    pass


@contextmanager
def sync_lock():
    lock = get_redis().lock(f"{_PREFIX}lock", timeout=90, blocking=False)
    if not lock.acquire():
        raise SyncBusy("Já existe uma sincronização em andamento")
    try:
        yield
    finally:
        try:
            lock.release()
        except LockError:
            logger.warning("A trava da sincronização expirou")


def _upsert_changed(items):
    if not items:
        return 0
    existing = vector_store.existing_products([product["id"] for product in items])
    changed = []
    for product in items:
        content = embeddings.product_content(product)
        previous = existing.get(product["id"], {})
        if (previous.get("conteudo"), previous.get("modelo_embedding")) != (
            content, embeddings.EMBEDDING_VERSION,
        ):
            changed.append((product, content))
    if not changed:
        return 0

    vectors = embeddings.embed_products([(product.get("nome") or "none", content) for product, content in changed])
    vector_store.upsert([
        {"produto_id": product["id"], "conteudo": content, "embedding": vector,
         "modelo_embedding": embeddings.EMBEDDING_VERSION}
        for (product, content), vector in zip(changed, vectors)
    ])
    return len(changed)


def index_page(after=None):
    with timeout(6):
        query = {"ativo": True}
        if after:
            query["_id"] = {"$gt": ObjectId(after)}
        docs = list(products.collection().find(query).sort("_id", 1).limit(BATCH_SIZE))
    count = _upsert_changed([products.serialize_product(doc) for doc in docs])
    return (str(docs[-1]["_id"]) if len(docs) == BATCH_SIZE else None), count


def prune_page(after=0):
    rows = vector_store.list_rows(after, 100)
    ids = [ObjectId(row["produto_id"]) for row in rows if ObjectId.is_valid(row["produto_id"])]
    active = set()
    if ids:
        with timeout(6):
            active = {str(doc["_id"]) for doc in products.collection().find(
                {"_id": {"$in": ids}, "ativo": True}, {"_id": 1},
            )}
    stale = [row["id"] for row in rows if row["produto_id"] not in active]
    vector_store.remove_rows(stale)
    return (rows[-1]["id"] if len(rows) == 100 else 0), len(stale)


def sync_product(product_id):
    with sync_lock():
        with timeout(6):
            product = products.get_product(product_id)
        if product:
            return {"indexados": _upsert_changed([product])}
        vector_store.remove_product(product_id)
        return {"remocao_verificada": True}


def reconcile_step():
    """Processa uma página de cada origem e só avança após a escrita correspondente."""
    with sync_lock():
        redis = get_redis()
        index_key = f"{_PREFIX}index_cursor"
        prune_key = f"{_PREFIX}prune_cursor"
        # Limpa órfãos mesmo se o provedor de embeddings estiver fora do ar.
        prune_cursor, removed = prune_page(int(redis.get(prune_key) or 0))
        redis.set(prune_key, prune_cursor)
        index_cursor, indexed = index_page(redis.get(index_key) or None)
        redis.set(index_key, index_cursor or "")
    return {"indexados": indexed, "removidos": removed,
            "mais_paginas": bool(index_cursor or prune_cursor)}


def notify_n8n(product_id):
    """Avisa o n8n depois da gravação do produto."""
    url = os.getenv("N8N_WEBHOOK_URL", "").strip()
    secret = os.getenv("N8N_WEBHOOK_SECRET", "").strip()
    if not url or len(secret) < 32:
        return
    try:
        target = httpx.URL(url)
        if target.scheme != "https" or not target.host or target.userinfo:
            logger.warning("Configure uma URL HTTPS para o webhook do n8n")
            return
        response = httpx.post(target, json={"produto_id": product_id},
                              headers={"X-Innova-Token": secret}, follow_redirects=False,
                              timeout=httpx.Timeout(10, connect=1.5))
        if not response.is_success:
            logger.warning("Aviso ao n8n pendente de reconciliação (HTTP %s)", response.status_code)
    except (httpx.HTTPError, httpx.InvalidURL, ValueError) as exc:
        logger.warning("Aviso ao n8n pendente de reconciliação (%s)", type(exc).__name__)
