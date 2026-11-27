"""Teste opcional com n8n Cloud, MongoDB e Supabase de homologação."""
import json
import os
import re
from math import isfinite
from time import monotonic, sleep
from uuid import uuid4

import httpx
import pytest
from dotenv import load_dotenv
from pymongo import timeout
from pymongo.errors import PyMongoError

from services import embeddings, products, vector_store


def _https_url(name):
    try:
        url = httpx.URL(os.getenv(name, "").strip())
    except (httpx.InvalidURL, ValueError):
        pytest.fail(f"Configure {name} com uma URL HTTPS válida.", pytrace=False)
    if url.scheme != "https" or not url.host or url.userinfo:
        pytest.fail(f"Configure {name} com uma URL HTTPS válida.", pytrace=False)
    return url


def _request(method, http, url, **kwargs):
    try:
        return http.request(method, url, **kwargs)
    except (httpx.HTTPError, httpx.InvalidURL, ValueError) as exc:
        pytest.fail(f"Falha de comunicação no teste ({type(exc).__name__}).", pytrace=False)


def _csrf_token(client, path):
    page = _request("GET", client, path)
    token = re.search(r'<meta name="csrf-token" content="([^"]+)"', page.text)
    if page.status_code != 200 or not token:
        pytest.fail(f"Falha ao abrir {path} e obter o CSRF (HTTP {page.status_code}).", pytrace=False)
    return token[1]


def _admin_post(client, path, data):
    response = _request("POST", client, path, data=data)
    if response.status_code != 302 or httpx.URL(response.headers.get("location", "")).path != "/admin/":
        pytest.fail(f"O painel não confirmou a operação {path} (HTTP {response.status_code}).", pytrace=False)


def _find(query):
    try:
        with timeout(6):
            return products.collection().find_one(query)
    except (PyMongoError, RuntimeError, ValueError) as exc:
        pytest.fail(f"Falha no MongoDB de teste ({type(exc).__name__}).", pytrace=False)


def _row(product_id):
    try:
        rows = vector_store._request("GET", vector_store.TABLE, params={
            "produto_id": f"eq.{product_id}", "select": "id,conteudo,embedding,modelo_embedding",
        })
    except vector_store.VectorStoreError as exc:
        pytest.fail(str(exc), pytrace=False)
    assert isinstance(rows, list) and len(rows) <= 1, "Era esperado no máximo um vetor por produto."
    return rows[0] if rows else None


def _wait(check, phase):
    deadline = monotonic() + 45
    while monotonic() < deadline:
        result = check()
        if result:
            return result
        sleep(1)
    pytest.fail(f"Tempo esgotado na etapa {phase}. Confira a execução no n8n e os logs do Flask.", pytrace=False)


@pytest.mark.skipif(os.getenv("INNOVA_SYNC_E2E") != "1", reason="Requer opt-in e serviços de homologação")
def test_sync_real():
    load_dotenv()
    app_url = _https_url("INNOVA_E2E_BASE_URL")
    webhook = _https_url("N8N_WEBHOOK_URL")
    for name in ("INNOVA_E2E_ADMIN_EMAIL", "INNOVA_E2E_ADMIN_PASSWORD", "N8N_WEBHOOK_SECRET", "INNOVA_SYNC_SECRET",
                 "MONGODB_URI", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"):
        if not (os.getenv(name) or "").strip():
            pytest.fail(f"Configure {name} no ambiente de teste.", pytrace=False)

    name = f"Sofá teste integração {uuid4().hex}"
    create = "/admin/produtos/novo"
    callback = "/api/rag/sync"
    form = {"nome": name, "categoria": "Sofás", "descricao": "Sofá de tecido azul com pés de madeira.",
            "preco": "987,65", "estoque": "1", "ativo": "on"}
    with httpx.Client(base_url=app_url, timeout=25, follow_redirects=False) as client:
        for auth in ({}, {"X-Sync-Token": "token-incorreto-de-teste"}):
            response = _request("POST", client, callback, headers=auth, json={})
            if response.status_code != 401:
                pytest.fail(f"O callback deveria responder 401. Recebeu HTTP {response.status_code}.", pytrace=False)
        response = _request("POST", client, callback, json={},
                            headers={"X-Sync-Token": os.environ["INNOVA_SYNC_SECRET"]})
        if response.status_code != 400:
            pytest.fail(f"O callback autenticado deveria rejeitar o JSON vazio com 400. Recebeu HTTP {response.status_code}.", pytrace=False)

        _admin_post(client, "/admin/login", {
            "csrf_token": _csrf_token(client, "/admin/login"),
            "email": os.environ["INNOVA_E2E_ADMIN_EMAIL"], "senha": os.environ["INNOVA_E2E_ADMIN_PASSWORD"],
        })
        form["csrf_token"] = _csrf_token(client, "/admin/")
        oid = None
        try:
            _admin_post(client, create, form)
            product = _find({"nome": name, "preco_centavos": 98765, "ativo": True})
            assert product, "O MongoDB de teste deve apontar para o catálogo usado pelo Flask."
            oid = product["_id"]
            delete = f"/admin/produtos/{oid}/excluir"
            edit = f"/admin/produtos/{oid}/editar"
            original = _wait(lambda: _row(oid), "indexação do cadastro")
            assert name in original["conteudo"] and "987,65" in original["conteudo"]
            assert original["modelo_embedding"] == embeddings.EMBEDDING_VERSION
            values = original["embedding"]
            values = json.loads(values) if isinstance(values, str) else values
            assert len(values) == embeddings.DIMENSIONS and all(map(isfinite, values)) and any(values)
            matches = vector_store.search(values, allowed_ids=[str(oid)], limit=1)
            assert matches and matches[0]["produto_id"] == str(oid) and matches[0]["similaridade"] > 0.99

            with httpx.Client(timeout=45, follow_redirects=False) as n8n:
                response = _request("POST", n8n, webhook, json={"produto_id": str(oid)},
                                    headers={"X-Innova-Token": os.environ["N8N_WEBHOOK_SECRET"]})
            if not response.is_success:
                pytest.fail(f"O n8n retornou HTTP {response.status_code} ao repetir o evento.", pytrace=False)
            assert _row(oid) == original, "A repetição deveria manter a mesma linha e o mesmo vetor."

            form.update(preco="1234,56", descricao="Sofá modular em couro caramelo com chaise.")
            _admin_post(client, edit, form)
            assert _find({"_id": oid, "preco_centavos": 123456, "ativo": True})

            def updated_row():
                row = _row(oid)
                return row if row and "1.234,56" in row["conteudo"] else None

            updated = _wait(updated_row, "sincronização da edição")
            assert updated["id"] == original["id"] and updated["embedding"] != original["embedding"]

            inactive = {**form, "ativo": ""}
            _admin_post(client, edit, inactive)
            assert _find({"_id": oid, "ativo": False})
            _wait(lambda: _row(oid) is None, "remoção após desativação")
            _admin_post(client, edit, form)
            _wait(updated_row, "reindexação após reativação")
            _admin_post(client, delete, {"csrf_token": form["csrf_token"]})
            assert _find({"_id": oid}) is None
            _wait(lambda: _row(oid) is None, "remoção após exclusão")
        finally:
            remaining = _find({"nome": name})
            if remaining:
                oid = remaining["_id"]
                _admin_post(client, f"/admin/produtos/{oid}/excluir", {"csrf_token": form["csrf_token"]})
                if _find({"_id": oid}) is not None:
                    pytest.fail("O painel não removeu o produto temporário.", pytrace=False)
            if oid and _row(oid):
                # Em caso de falha no workflow, limpa somente o vetor da fixture já excluída.
                vector_store.remove_product(str(oid))
