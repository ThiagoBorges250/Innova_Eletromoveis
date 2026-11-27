"""Embeddings do catálogo via Gemini, sem pesos locais."""
import json
import math
import os

import httpx

from services.products import format_brl

MODEL = "gemini-embedding-2"
DIMENSIONS = 384
# Invalide os vetores armazenados se o modelo ou os prefixos mudarem.
EMBEDDING_VERSION = f"{MODEL}:{DIMENSIONS}:v1"
_API = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiError(RuntimeError):
    pass


def gemini_request(operation, payload, *, timeout):
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise GeminiError("GEMINI_API_KEY ausente")
    try:
        response = httpx.post(f"{_API}/{operation}", json=payload,
                              headers={"x-goog-api-key": key}, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        raise GeminiError(f"Gemini HTTP {exc.response.status_code}") from None
    except (httpx.HTTPError, ValueError) as exc:
        raise GeminiError(f"Gemini: {type(exc).__name__}") from None


def product_content(product):
    characteristics = product.get("caracteristicas") or ""
    if not isinstance(characteristics, str):
        characteristics = json.dumps(characteristics, ensure_ascii=False, sort_keys=True,
                                     default=str)
    return "\n".join((
        f"Nome: {product.get('nome', '')}",
        f"Categoria: {product.get('categoria', '')}",
        f"Preço: {format_brl(product['preco_centavos'])}",
        f"Características: {characteristics[:1500]}",
        f"Descrição: {str(product.get('descricao') or '')[:2000]}",
    ))


def _embedding_payload(text):
    return {"model": f"models/{MODEL}", "content": {"parts": [{"text": text}]},
            "outputDimensionality": DIMENSIONS}


def _vector(result):
    try:
        values = result["values"]
        if (len(values) != DIMENSIONS
                or not all(type(value) in (int, float) and math.isfinite(value) for value in values)
                or not any(values)):
            raise ValueError
    except (KeyError, TypeError, ValueError, OverflowError):
        raise GeminiError("Embedding inválido") from None
    return values


def embed_query(question):
    payload = _embedding_payload(f"task: search result | query: {question}")
    response = gemini_request(f"{MODEL}:embedContent", payload, timeout=5)
    if not isinstance(response, dict):
        raise GeminiError("Resposta de embedding inválida")
    return _vector(response.get("embedding"))


def embed_products(products):
    requests = [_embedding_payload(f"title: {name} | text: {content}")
                for name, content in products]
    response = gemini_request(f"{MODEL}:batchEmbedContents", {"requests": requests}, timeout=12)
    embeddings = response.get("embeddings") if isinstance(response, dict) else None
    if not isinstance(embeddings, list) or len(embeddings) != len(requests):
        raise GeminiError("Quantidade inesperada de embeddings")
    return [_vector(embedding) for embedding in embeddings]
