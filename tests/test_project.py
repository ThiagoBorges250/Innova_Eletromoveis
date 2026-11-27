"""Testes locais sem conexões a serviços externos."""
from urllib.parse import unquote, urlparse, parse_qs
from datetime import datetime, timezone

import mongomock
import pytest

from services.products import format_brl, parse_price
from services.cart import whatsapp_link, whatsapp_message


@pytest.fixture()
def client(monkeypatch):
    db = mongomock.MongoClient().get_database("test_innova")
    monkeypatch.setenv("N8N_WEBHOOK_URL", "")
    monkeypatch.setenv("REDIS_URL", "")
    monkeypatch.setattr("services.products.collection", lambda: db["produtos"])
    from app import create_app
    app = create_app({"TESTING": True, "SECRET_KEY": "test-secret-only", "WTF_CSRF_ENABLED": False})
    with app.test_client() as test_client:
        yield test_client, db


def test_prices():
    assert parse_price("1.899,90") == 189990
    assert parse_price("1899.90") == 189990
    assert format_brl(189990) == "R$ 1.899,90"
    with pytest.raises(ValueError):
        parse_price("-10")
    with pytest.raises(ValueError):
        parse_price("0")


def test_catalog_add_to_cart_and_checkout(client, monkeypatch):
    http, db = client
    id = db.produtos.insert_one({
        "nome": "Sofá de teste", "categoria": "Sofás", "preco_centavos": 12345,
        "descricao": "Teste", "estoque": 3, "imagem": "/static/img/sofa.svg",
        "ativo": True, "destaque": True, "criado_em": datetime.now(timezone.utc),
    }).inserted_id
    pid = str(id)
    home = http.get("/")
    assert home.status_code == 200
    assert b"Sof\xc3\xa1 de teste" in home.data
    detail = http.get(f"/produto/{pid}")
    assert detail.status_code == 200
    response = http.post("/carrinho/adicionar", data={"produto_id": pid, "quantidade": "2"}, headers={"Accept": "application/json"})
    assert response.status_code == 200
    assert response.json["quantidade"] == 2
    cart = http.get("/carrinho")
    assert b"R$ 246,90" in cart.data
    assert b"Visualizar mensagem do WhatsApp" in cart.data
    assert b"Quantidade: 2" in cart.data
    monkeypatch.setenv("WHATSAPP_NUMBER", "5589981342222")
    buy = http.get("/comprar", follow_redirects=False)
    assert buy.status_code == 302
    assert buy.location.startswith("https://wa.me/5589981342222?text=")
    assert "2x Sofá de teste" in unquote(buy.location)
    assert "Total: R$ 246,90" in unquote(buy.location)
    http.post("/carrinho/remover", data={"produto_id": pid})
    assert b"Seu carrinho est\xc3\xa1 vazio" in http.get("/carrinho").data


def test_admin_is_restricted_and_insert_immediately_visible(client, monkeypatch):
    http, db = client
    assert http.get("/admin/").status_code == 302
    monkeypatch.setattr("routes.admin.authenticate_admin", lambda email, password: {"id": "valid-uid", "email": email})
    monkeypatch.setattr("routes.admin.is_admin", lambda user_id: user_id == "valid-uid")
    result = http.post("/admin/login", data={"email": "admin@test.com", "senha": "correct"})
    assert result.status_code == 302
    assert result.location.endswith("/admin/")
    response = http.post("/admin/produtos/novo", data={
        "nome": "Guarda-roupas novo", "categoria": "Guarda-roupas", "preco": "999,90",
        "descricao": "Produto recém-cadastrado", "estoque": "2", "ativo": "on",
    })
    assert response.status_code == 302
    assert db.produtos.count_documents({}) == 1
    assert b"Guarda-roupas novo" in http.get("/").data
    assert b"Guarda-roupas novo" in http.get("/admin/").data


def test_stock_limits_and_invalid_id(client):
    http, db = client
    pid = str(db.produtos.insert_one({
        "nome": "Fogão teste", "categoria": "Fogões", "preco_centavos": 70000,
        "estoque": 1, "ativo": True, "criado_em": datetime.now(timezone.utc),
    }).inserted_id)
    res = http.post("/carrinho/adicionar", data={"produto_id": pid, "quantidade": "10"}, headers={"Accept": "application/json"})
    assert res.status_code == 200
    assert res.json["quantidade"] == 1
    assert http.get("/produto/nao-existe").status_code == 404


def test_whatsapp_message_format(monkeypatch):
    monkeypatch.setenv("WHATSAPP_NUMBER", "5589981342222")
    link = whatsapp_link([{"quantidade": 1, "produto": {"nome": "Sofá", "preco_centavos": 189990}, "subtotal": 189990}], 189990)
    assert "Total: R$ 1.899,90" in unquote(link)


def test_whatsapp_message_multiple_items_with_subtotals(monkeypatch):
    monkeypatch.setenv("WHATSAPP_NUMBER", "5589981342222")
    rows = [
        {"quantidade": 1, "produto": {"nome": "Sofá Retrátil", "preco_centavos": 189990}, "subtotal": 189990},
        {"quantidade": 2, "produto": {"nome": "Fogão 4 Bocas", "preco_centavos": 74990}, "subtotal": 149980},
    ]
    total = 339970
    expected = whatsapp_message(rows, total)
    link = whatsapp_link(rows, total)
    parsed = urlparse(link)
    assert parsed.scheme == "https"
    assert parsed.netloc == "wa.me"
    assert parsed.path == "/5589981342222"
    message = parse_qs(parsed.query)["text"][0]
    assert message == expected
    assert "1. *Sofá Retrátil*" in message
    assert "2. *Fogão 4 Bocas*" in message
    assert "Quantidade: 2" in message
    assert "Preço unitário: R$ 749,90" in message
    assert "Subtotal: R$ 1.499,80" in message
    assert "Total: R$ 3.399,70" in message


def test_whatsapp_message_rejects_inconsistent_total():
    with pytest.raises(ValueError):
        whatsapp_message([{"quantidade": 2, "produto": {"nome": "Sofá", "preco_centavos": 10000}, "subtotal": 20000}], 10000)


def test_whatsapp_message_rejects_empty_cart():
    with pytest.raises(ValueError):
        whatsapp_message([], 0)


def test_home_carousel_only_in_stock_products(client):
    http, db = client
    now = datetime.now(timezone.utc)
    sofa_id = db.produtos.insert_one({
        "nome": "Sofá Premium", "categoria": "Sofás", "preco_centavos": 235000,
        "estoque": 2, "imagem": "/static/img/sofa.svg", "ativo": True,
        "destaque": True, "criado_em": now,
    }).inserted_id
    db.produtos.insert_one({
        "nome": "Sofá esgotado", "categoria": "Sofás", "preco_centavos": 50000,
        "estoque": 0, "ativo": True, "destaque": True, "criado_em": now,
    })
    response = http.get("/")
    assert response.status_code == 200
    assert b'data-hero-carousel' in response.data
    assert "Sofá Premium".encode() in response.data
    assert b'href="/produto/' + str(sofa_id).encode() + b'"' in response.data
    hero = response.data.split(b'data-hero-carousel', 1)[1].split(b'</section>', 1)[0]
    assert "Sofá esgotado".encode() not in hero
    assert b'R$ 2.350,00' in hero


def test_home_carousel_falls_back_when_no_products(client):
    http, _ = client
    page = http.get("/").data
    assert b'hero-room.svg' in page
    assert b'data-hero-carousel' not in page
