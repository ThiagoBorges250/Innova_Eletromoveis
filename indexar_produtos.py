"""Indexa os produtos ativos e remove vetores órfãos. Execute com python indexar_produtos.py."""
from dotenv import load_dotenv
from pymongo.errors import PyMongoError
from redis.exceptions import RedisError

from services.vector_sync import index_page, prune_page, sync_lock


def main():
    load_dotenv()
    indexed = removed = 0
    try:
        cursor = None
        while True:
            with sync_lock():
                cursor, count = index_page(cursor)
            indexed += count
            print(f"Vetores gravados até agora: {indexed}", flush=True)
            if cursor is None:
                break

        cursor = 0
        while True:
            with sync_lock():
                cursor, count = prune_page(cursor)
            removed += count
            if not cursor:
                break
    except (PyMongoError, RedisError, RuntimeError, ValueError) as exc:
        detail = str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__
        print(f"Indexação interrompida ({detail}). Execute novamente para concluir.")
        return 1
    print(f"Indexação concluída. {indexed} vetores gravados e {removed} removidos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
