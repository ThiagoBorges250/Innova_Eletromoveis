"""Regressões do assistente e da sincronização sem usar serviços externos."""
import json
from contextlib import nullcontext

import httpx
import mongomock
import pytest

from services import embeddings, products, rag, vector_store, vector_sync


@pytest.fixture
def catalog(monkeypatch):
    collection = mongomock.MongoClient().test_innova.produtos
    monkeypatch.setattr(products, "collection", lambda: collection)
    return collection


def add_product(catalog, **changes):
    doc = {"nome": "Sofá de teste", "categoria": "Sofás", "preco_centavos": 189990,
           "estoque": 2, "ativo": True, "descricao": "Tecido cinza.",
           "caracteristicas": {"lugares": 3}}
    doc.update(changes)
    return catalog.insert_one(doc).inserted_id


@pytest.mark.parametrize(("question", "minimum", "maximum"), [
    ("Sofás até R$ 2.000", None, 200000),
    ("Sofás abaixo de 2,5 mil", None, 249999),
    ("Geladeira entre R$ 1.200 e R$ 2.000,50", 120000, 200050),
    ("Lavadoras de 12 a 14 kg", None, None),
    ("Lavadora de até 12 kg", None, None),
    ("Cama acima de R$ 900", 90001, None),
])
def test_filters(question, minimum, maximum):
    _, filters = rag.resolve_query(question, [], None, None)
    assert (filters.minimum, filters.maximum) == (minimum, maximum)


def test_embeddings_share_the_model_and_check_dimensions(monkeypatch):
    vector = [1.0] + [0.0] * 383

    def gemini(operation, payload, **kwargs):
        request = payload.get("requests", [payload])[0]
        assert request["model"] == f"models/{embeddings.MODEL}"
        assert request["outputDimensionality"] == 384
        if operation.endswith(":batchEmbedContents"):
            return {"embeddings": [{"values": vector}]}
        return {"embedding": {"values": vector}}

    monkeypatch.setattr(embeddings, "gemini_request", gemini)
    assert embeddings.embed_query("Sofá retrátil") == vector
    assert embeddings.embed_products([("Sofá", "Retrátil")]) == [vector]
    vector.pop()
    with pytest.raises(embeddings.GeminiError):
        embeddings.embed_query("Sofá retrátil")


def test_chat_launcher_renders_on_catalog_pages_when_queries_are_paused(catalog, monkeypatch):
    from app import create_app

    monkeypatch.setenv("INNOVA_AI_ENABLED", "0")
    monkeypatch.setenv("REDIS_URL", "")
    pid = add_product(catalog)
    app = create_app({"TESTING": True, "SECRET_KEY": "teste"})
    client = app.test_client()
    for path in ("/", "/?categoria=Sof%C3%A1s", f"/produto/{pid}", "/carrinho"):
        response = client.get(path)
        assert response.status_code == 200
        assert b"Fale com a IA" in response.data
        assert b'/static/css/innova-ai.css' in response.data
        assert b'/static/js/innova-ai.js' in response.data
        assert b'data-endpoint="/api/innova-ai/perguntar"' in response.data

    assert b"Fale com a IA" not in client.get("/admin/login").data
    token = client.get("/").data.split(b'name="csrf-token" content="')[1].split(b'"')[0].decode()
    response = client.post("/api/innova-ai/perguntar", json={"pergunta": "Sofás"},
                           headers={"X-CSRFToken": token})
    assert response.status_code == 503
    assert "temporariamente indisponível" in response.json["error"]


def test_assistant_revalidates_price_and_never_returns_model_invented_ids(catalog, monkeypatch):
    from app import create_app

    monkeypatch.delenv("INNOVA_AI_ENABLED", raising=False)
    selected = add_product(catalog)
    sold_out = add_product(catalog, estoque=0)
    outside_budget = add_product(catalog, preco_centavos=250000)
    another_category = add_product(catalog, categoria="Camas")
    monkeypatch.setattr("routes.innova_ai._retry_after", lambda: 0)
    monkeypatch.setattr(embeddings, "embed_query", lambda question: [1.0] * 384)

    def search(embedding, *, limit, allowed_ids):
        assert allowed_ids == [str(selected)]
        # Simula resultados desatualizados ou inesperados vindos do banco vetorial.
        return [{"produto_id": str(pid), "similaridade": 0.9}
                for pid in (sold_out, outside_budget, another_category, selected)]

    def gemini(operation, payload, **kwargs):
        context = json.loads(payload["contents"][0]["parts"][0]["text"])
        assert [item["id"] for item in context["catalogo"]] == [str(selected)]
        assert "R$ 1.899,90" in context["catalogo"][0]["dados"]
        catalog.update_one({"_id": selected}, {"$set": {"preco_centavos": 179990}})
        fake = json.dumps({"estilo": "recomendar", "ids": ["inventado"], "resposta": "R$ 1"})
        return {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": fake}]}}]}

    monkeypatch.setattr(vector_store, "search", search)
    monkeypatch.setattr(embeddings, "gemini_request", gemini)
    flask_app = create_app({"TESTING": True, "SECRET_KEY": "teste", "SESSION_COOKIE_SECURE": True})
    client = flask_app.test_client()
    endpoint = "/api/innova-ai/perguntar"
    question = {"pergunta": "Sofás até R$ 2.000"}
    origin = "https://innova.test"
    assert client.post(endpoint, base_url=origin, json=question).status_code == 400
    page = client.get("/", base_url=origin)
    token = page.data.split(b'name="csrf-token" content="')[1].split(b'"')[0].decode()
    headers = {"X-CSRFToken": token, "Referer": f"{origin}/"}
    res = client.post(endpoint, base_url=origin, json=question, headers=headers)
    assert res.status_code == 200
    assert res.headers["Cache-Control"] == "no-store"
    assert [item["id"] for item in res.json["produtos"]] == [str(selected)]
    assert res.json["produtos"][0]["preco"] == "R$ 1.799,90"
    assert "inventado" not in res.get_data(as_text=True)

    monkeypatch.setattr("routes.innova_ai._retry_after", lambda: 17)
    res = client.post(endpoint, base_url=origin, json=question, headers=headers)
    assert res.status_code == 429 and res.headers["Retry-After"] == "17"


def test_webhook_upserts_idempotently_and_removes_inactive_and_deleted(catalog, monkeypatch):
    from app import create_app

    pid = add_product(catalog)
    stored = {}
    secret = "teste-de-sincronizacao-que-tem-32-caracteres"
    monkeypatch.setenv("INNOVA_SYNC_SECRET", secret)
    monkeypatch.setattr(vector_sync, "sync_lock", nullcontext)
    monkeypatch.setattr(vector_store, "existing_products", lambda ids: stored)
    monkeypatch.setattr(vector_store, "upsert", lambda rows: stored.update((row["produto_id"], row) for row in rows))
    monkeypatch.setattr(vector_store, "remove_product", lambda key: stored.pop(key, None))
    monkeypatch.setattr(embeddings, "embed_products", lambda docs: [[1.0] * 384 for _ in docs])
    client = create_app({"TESTING": True, "SECRET_KEY": "teste"}).test_client()
    endpoint = "/api/rag/sync"
    data = {"produto_id": str(pid)}
    assert client.post(endpoint, json=data).status_code == 401
    assert client.post(endpoint, json=data, headers={"X-Sync-Token": "incorreto"}).status_code == 401
    assert client.post(endpoint, json=data, headers={"X-Innova-Token": secret}).status_code == 401
    headers = {"X-Sync-Token": secret}
    assert client.get(endpoint, headers=headers).status_code == 405
    assert client.post(endpoint, json={"produto_id": "invalido"}, headers=headers).status_code == 400
    assert client.post(endpoint, json=data, headers=headers).json["indexados"] == 1
    assert "lugares" in stored[str(pid)]["conteudo"]
    assert client.post(endpoint, json=data, headers=headers).json["indexados"] == 0
    catalog.update_one({"_id": pid}, {"$set": {"preco_centavos": 170000}})
    assert client.post(endpoint, json=data, headers=headers).json["indexados"] == 1
    assert len(stored) == 1 and "R$ 1.700,00" in stored[str(pid)]["conteudo"]
    catalog.update_one({"_id": pid}, {"$set": {"ativo": False}})
    assert client.post(endpoint, json=data, headers=headers).status_code == 200
    assert not stored
    catalog.delete_one({"_id": pid})
    assert client.post(endpoint, json=data, headers=headers).status_code == 200
    assert not stored


def test_scheduled_reconciliation_retries_failed_page_and_removes_orphans(catalog, monkeypatch):
    active = add_product(catalog)
    inactive = add_product(catalog, ativo=False)
    cursors = {}

    class RedisCursors:
        get = cursors.get

        def set(self, key, value):
            cursors[key] = value

    monkeypatch.setattr(vector_sync, "get_redis", RedisCursors)
    monkeypatch.setattr(vector_sync, "sync_lock", nullcontext)
    monkeypatch.setattr(vector_sync, "BATCH_SIZE", 1)
    rows = [{"id": 3, "produto_id": str(active)}, {"id": 4, "produto_id": str(inactive)}]
    monkeypatch.setattr(vector_store, "list_rows", lambda after, limit: rows[:])

    def remove(ids):
        rows[:] = [row for row in rows if row["id"] not in ids]

    monkeypatch.setattr(vector_store, "remove_rows", remove)
    monkeypatch.setattr(vector_store, "existing_products", lambda ids: {})

    def unavailable(docs):
        raise embeddings.GeminiError("Provedor indisponível")

    monkeypatch.setattr(embeddings, "embed_products", unavailable)
    with pytest.raises(embeddings.GeminiError):
        vector_sync.reconcile_step()
    assert rows == [{"id": 3, "produto_id": str(active)}]
    assert not cursors.get("innova:ai:sync:index_cursor")

    monkeypatch.setattr(embeddings, "embed_products", lambda docs: [[1.0] * 384 for _ in docs])
    written = []
    monkeypatch.setattr(vector_store, "upsert", written.extend)
    assert vector_sync.reconcile_step() == {"indexados": 1, "removidos": 0, "mais_paginas": True}
    assert written[0]["produto_id"] == str(active)
    assert vector_sync.reconcile_step() == {"indexados": 0, "removidos": 0, "mais_paginas": False}


def test_n8n_timeout_leaves_product_write_available(catalog, monkeypatch):
    from app import create_app

    monkeypatch.setenv("N8N_WEBHOOK_URL", "https://n8n.example.test/webhook/innova-produtos")
    monkeypatch.setenv("N8N_WEBHOOK_SECRET", "teste-de-webhook-com-32-caracteres")

    def offline(*args, **kwargs):
        raise httpx.ConnectTimeout("n8n offline")

    monkeypatch.setattr(httpx, "post", offline)
    monkeypatch.setattr("routes.admin.is_admin", lambda uid: uid == "test-admin")
    client = create_app({"TESTING": True, "SECRET_KEY": "teste", "WTF_CSRF_ENABLED": False}).test_client()
    with client.session_transaction() as session:
        session["admin_id"] = "test-admin"
    response = client.post("/admin/produtos/novo", data={
        "nome": "Sofá após falha do n8n", "categoria": "Sofás", "preco": "1899,90", "ativo": "on",
    })
    assert response.status_code == 302
    assert catalog.find_one({"nome": "Sofá após falha do n8n", "ativo": True})


def test_admin_events_reach_sync_callback_via_n8n_contract(catalog, monkeypatch):
    from app import create_app

    url = "https://n8n.example.test/webhook/innova-produtos"
    outbound = "segredo-de-saida-do-n8n-com-32-caracteres"
    inbound = "segredo-do-callback-com-32-caracteres"
    monkeypatch.setenv("N8N_WEBHOOK_URL", url)
    monkeypatch.setenv("N8N_WEBHOOK_SECRET", outbound)
    monkeypatch.setenv("INNOVA_SYNC_SECRET", inbound)
    monkeypatch.setattr("routes.admin.is_admin", lambda uid: uid == "test-admin")
    app = create_app({"TESTING": True, "SECRET_KEY": "teste"})
    admin = app.test_client()
    n8n = app.test_client()
    index_events = []
    monkeypatch.setattr(vector_sync, "sync_lock", nullcontext)
    monkeypatch.setattr(vector_sync, "_upsert_changed", lambda items: index_events.append(items[0]["preco_centavos"]) or 1)
    monkeypatch.setattr(vector_store, "remove_product", lambda pid: index_events.append(None))

    def forward(target, *, json, headers, **kwargs):
        assert str(target) == url
        assert headers == {"X-Innova-Token": outbound}
        assert not kwargs["follow_redirects"]
        callback = n8n.post("/api/rag/sync", json=json, headers={"X-Sync-Token": inbound})
        return httpx.Response(callback.status_code, json=callback.json)

    monkeypatch.setattr(httpx, "post", forward)
    page = admin.get("/admin/login")
    csrf = page.data.split(b'name="csrf-token" content="')[1].split(b'"')[0].decode()
    with admin.session_transaction() as session:
        session["admin_id"] = "test-admin"
    product = {"nome": "Sofá sincronizado", "categoria": "Sofás", "preco": "1999,90",
               "ativo": "on", "csrf_token": csrf}
    assert admin.post("/admin/produtos/novo", data=product).status_code == 302
    pid = catalog.find_one({"nome": product["nome"]})["_id"]
    assert admin.post(f"/admin/produtos/{pid}/editar", data={**product, "preco": "1799,90"}).status_code == 302
    assert admin.post(f"/admin/produtos/{pid}/excluir", data={"csrf_token": csrf}).status_code == 302
    assert catalog.find_one({"_id": pid}) is None
    assert index_events == [199990, 179990, None]
