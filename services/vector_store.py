"""Acesso à Data API do Supabase dedicado ao índice vetorial."""
import json
import os

import httpx

from services.embeddings import EMBEDDING_VERSION

TABLE = "produtos_vetoriais"


class VectorStoreError(RuntimeError):
    pass


def _request(method, path, *, params=None, payload=None, prefer=None):
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        raise VectorStoreError("Supabase vetorial sem configuração")
    headers = {"apikey": key}
    if key.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {key}"
    if prefer:
        headers["Prefer"] = prefer
    try:
        response = httpx.request(method, f"{url}/rest/v1/{path}", params=params,
                                 json=payload, headers=headers, timeout=4)
        response.raise_for_status()
        if response.content:
            return response.json()
    except httpx.HTTPStatusError as exc:
        raise VectorStoreError(f"Supabase vetorial HTTP {exc.response.status_code}") from None
    except (httpx.HTTPError, httpx.InvalidURL, ValueError) as exc:
        raise VectorStoreError(f"Supabase vetorial: {type(exc).__name__}") from None


def search(embedding, *, allowed_ids=None, limit=40):
    return _request("POST", "rpc/buscar_produtos", payload={
        "embedding_consulta": json.dumps(embedding, separators=(",", ":")),
        "modelo_consulta": EMBEDDING_VERSION,
        "limite": limit,
        "ids_permitidos": allowed_ids,
    })


def existing_products(ids):
    rows = _request("GET", TABLE, params={
        "produto_id": f"in.({','.join(ids)})", "select": "produto_id,conteudo,modelo_embedding",
    })
    return {row["produto_id"]: row for row in rows}


def upsert(rows):
    _request("POST", TABLE, params={"on_conflict": "produto_id"}, payload=rows,
             prefer="resolution=merge-duplicates,return=minimal")


def list_rows(after, limit):
    return _request("GET", TABLE, params={
        "id": f"gt.{after}", "select": "id,produto_id", "order": "id.asc", "limit": limit,
    })


def remove_rows(ids):
    if ids:
        _request("DELETE", TABLE, params={"id": f"in.({','.join(map(str, ids))})"})


def remove_product(product_id):
    _request("DELETE", TABLE, params={"produto_id": f"eq.{product_id}"})
