"""Histórico de até 6 produtos vistos, mantido no Redis por 7 dias."""
from secrets import token_urlsafe

from flask import session
from redis.exceptions import RedisError
from services.db import get_redis
from services.products import get_products_by_ids

RECENT_LIMIT = 6
TTL_SECONDS = 7 * 24 * 60 * 60


def _key():
    visitor = session.get("visitor_id")
    if not visitor:
        visitor = token_urlsafe(20)
        session["visitor_id"] = visitor
    return f"innova:recentes:{visitor}"


def register_view(product_id):
    try:
        key = _key()
        with get_redis().pipeline(transaction=True) as pipe:
            pipe.lrem(key, 0, str(product_id))
            pipe.lpush(key, str(product_id))
            pipe.ltrim(key, 0, RECENT_LIMIT - 1)
            pipe.expire(key, TTL_SECONDS)
            pipe.execute()
        return True
    except (RedisError, RuntimeError, ValueError):
        return False


def load_recent_products():
    if not session.get("visitor_id"):
        return []
    try:
        ids = get_redis().lrange(_key(), 0, RECENT_LIMIT - 1)
        docs = get_products_by_ids(ids)
        return [docs[pid] for pid in ids if pid in docs]
    except (RedisError, RuntimeError, ValueError):
        return []
