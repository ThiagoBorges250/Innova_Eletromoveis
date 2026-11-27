"""API pública de compras e webhook interno usado pelo n8n."""
import hashlib
import os
from hmac import compare_digest
from ipaddress import ip_address, ip_network

from bson import ObjectId
from flask import Blueprint, current_app, jsonify, request, url_for
from pymongo.errors import PyMongoError
from redis.exceptions import RedisError

from services import rag, vector_sync
from services.db import get_redis
from services.products import CATEGORIES, format_brl

bp = Blueprint("innova_ai", __name__)
LIMIT_WINDOW = 60
_RATE_SCRIPT = """
for i = 1, 2 do
    if tonumber(redis.call('GET', KEYS[i]) or 0) >= tonumber(ARGV[i]) then
        return math.max(redis.call('TTL', KEYS[i]), 1)
    end
end
for i = 1, 2 do
    if redis.call('INCR', KEYS[i]) == 1 then
        redis.call('EXPIRE', KEYS[i], ARGV[3])
    end
end
return 0
"""


def _retry_after():
    address = request.remote_addr
    if current_app.config["INNOVA_AI_ON_VERCEL"]:
        address = request.headers.get("X-Vercel-Forwarded-For") or address
    try:
        ip = ip_address(address or "")
        if ip.version == 6 and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        identifier = str(ip_network((ip, 64), strict=False)) if ip.version == 6 else str(ip)
    except ValueError:
        identifier = "sem-ip"
    digest = hashlib.sha256(identifier.encode()).hexdigest()
    return get_redis().eval(_RATE_SCRIPT, 2, f"{{innova-ai}}:ip:{digest}", "{innova-ai}:global",
                            8, 60, LIMIT_WINDOW)


def _string(value):
    return isinstance(value, str) and 0 < len(value.strip()) <= rag.MAX_QUESTION


def _card(product):
    image = product["imagem"]
    # As fotos atuais da loja são locais e o upload administrativo gera URLs sob /static/.
    if not image.startswith("/static/"):
        image = url_for("static", filename="img/sem-foto.svg")
    return {
        "id": product["id"], "nome": product["nome"], "categoria": product["categoria"],
        "preco_centavos": product["preco_centavos"], "preco": format_brl(product["preco_centavos"]),
        "disponivel": True, "imagem": image,
        "url": url_for("shop.product_detail", product_id=product["id"]),
    }


@bp.after_request
def _disable_cache(response):
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.post("/api/innova-ai/perguntar")
def ask():
    if not current_app.config["INNOVA_AI_ENABLED"]:
        return jsonify(error="O Innova AI está temporariamente indisponível. Tente novamente mais tarde."), 503
    request.max_content_length = 8192
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not _string(data.get("pergunta")):
        return jsonify(error=f"Escreva uma pergunta de até {rag.MAX_QUESTION} caracteres."), 400
    history = data.get("historico", [])
    category = data.get("categoria", "")
    budget = data.get("orcamento_maximo", "")
    if not isinstance(history, list) or len(history) > 2 or not all(map(_string, history)):
        return jsonify(error="Histórico inválido."), 400
    if not isinstance(category, str) or (category and category not in CATEGORIES):
        return jsonify(error="Escolha uma categoria do catálogo."), 400
    if not isinstance(budget, str) or len(budget) > 32:
        return jsonify(error="Informe um orçamento válido."), 400
    try:
        maximum = rag.parse_budget(budget.strip().casefold()) if budget.strip() else None
        retry_after = _retry_after()
        if retry_after:
            return (jsonify(error="Você atingiu o limite de consultas. Tente novamente em instantes."),
                    429, {"Retry-After": str(retry_after)})
        message, items = rag.answer(data["pergunta"].strip(), [item.strip() for item in history],
                                    category=category, maximum=maximum)
        return jsonify(resposta=message, produtos=[_card(item) for item in items])
    except rag.InvalidQuery as exc:
        return jsonify(error=str(exc)), 400
    except (PyMongoError, RedisError, RuntimeError, ValueError) as exc:
        current_app.logger.warning("Consulta Innova AI indisponível (%s)", type(exc).__name__)
        return jsonify(error="Não consegui consultar o catálogo agora. Tente novamente em instantes."), 503


@bp.post("/api/rag/sync")
def synchronize():
    secret = os.getenv("INNOVA_SYNC_SECRET", "").strip()
    if len(secret) < 32:
        return jsonify(error="Sincronização indisponível."), 503
    if not compare_digest(request.headers.get("X-Sync-Token", "").encode(), secret.encode()):
        return jsonify(error="Acesso negado."), 401
    request.max_content_length = 1024
    data = request.get_json(silent=True)
    if isinstance(data, dict) and data.keys() == {"produto_id"}:
        product_id = data["produto_id"]
        if not isinstance(product_id, str) or not ObjectId.is_valid(product_id):
            return jsonify(error="Identificador de produto inválido."), 400
        operation = lambda: vector_sync.sync_product(str(ObjectId(product_id)))
    elif data == {"modo": "reconciliar"}:
        operation = vector_sync.reconcile_step
    else:
        return jsonify(error="Informe produto_id ou o modo reconciliar."), 400
    try:
        return jsonify(operation())
    except (PyMongoError, RedisError, RuntimeError, ValueError) as exc:
        current_app.logger.warning("Sincronização Innova AI pendente (%s)", type(exc).__name__)
        return jsonify(error="Sincronização pendente. Tente novamente."), 503, {"Retry-After": "5"}
