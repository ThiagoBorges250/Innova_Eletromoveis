
import os
from functools import lru_cache

from pymongo import MongoClient
from redis import Redis


@lru_cache(maxsize=1)
def get_mongo_client():
    uri = os.getenv("MONGODB_URI", "").strip()
    if not uri:
        raise RuntimeError("MONGODB_URI não configurada no .env")
    return MongoClient(uri, serverSelectionTimeoutMS=4000, connectTimeoutMS=4000)


def get_database():
    name = os.getenv("MONGODB_DB", "innova_eletromoveis")
    return get_mongo_client()[name]


@lru_cache(maxsize=1)
def get_redis():
    uri = os.getenv("REDIS_URL", "").strip()
    if not uri:
        raise RuntimeError("REDIS_URL não configurada no .env")
    return Redis.from_url(uri, decode_responses=True, socket_connect_timeout=3, socket_timeout=3)
