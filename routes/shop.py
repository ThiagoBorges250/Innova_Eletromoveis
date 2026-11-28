"""Rotas públicas: catálogo, detalhes, carrinho e WhatsApp."""
from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
from pymongo.errors import PyMongoError

from services.cart import MAX_QTY, cart_details, current_cart, set_quantity, whatsapp_link, whatsapp_message
from services.products import CATEGORIES, get_product, list_products
from services.recent import load_recent_products, register_view

bp = Blueprint("shop", __name__)

def _is_ajax():
    return "application/json" in request.headers.get("Accept", "")


def _respond(message, *, ok=True, status=200):
    if _is_ajax():
        return jsonify(ok=ok, mensagem=message, quantidade=sum(current_cart().values())), status
    flash(message, "success" if ok else "error")
    if not ok:
        return redirect(url_for("shop.cart"))
    return redirect(url_for("shop.index"))


@bp.route("/")
def index():
    category = request.args.get("categoria", "").strip()
    search = request.args.get("busca", "").strip()[:80]
    category = category if category in CATEGORIES else ""
    try:
        produtos = list_products(category=category, search=search, limit=80)
        hero_products = [] if category or search else list_products(featured_in_stock=True, limit=8)
        recentes = load_recent_products()
        mongo_error = False
    except (PyMongoError, RuntimeError, ValueError):
        produtos, hero_products, recentes, mongo_error = [], [], [], True
    return render_template("index.html", produtos=produtos, hero_products=hero_products,
                           recentes=recentes, categoria_atual=category, busca=search,
                           mongo_error=mongo_error)


@bp.route("/produto/<product_id>")
def product_detail(product_id):
    try:
        product = get_product(product_id)
    except (PyMongoError, RuntimeError):
        return render_template("error.html", code=503, message="Catálogo temporariamente indisponível."), 503
    if not product:
        return render_template("error.html", code=404, message="Produto não encontrado."), 404
    register_view(product_id)
    return render_template("product.html", produto=product)


@bp.route("/carrinho")
def cart():
    try:
        rows, total = cart_details()
    except (PyMongoError, RuntimeError, ValueError):
        return render_template("error.html", code=503, message="Não foi possível consultar o carrinho."), 503
    return render_template("cart.html", itens=rows, total=total,
                           mensagem_whatsapp=whatsapp_message(rows, total) if rows else "")


@bp.post("/carrinho/adicionar")
def add_to_cart():
    product_id = request.form.get("produto_id", "")
    try:
        qty = int(request.form.get("quantidade", 1))
    except (TypeError, ValueError):
        return _respond("Quantidade inválida.", ok=False, status=400)
    if qty < 1 or qty > MAX_QTY:
        return _respond(f"Escolha de 1 a {MAX_QTY} unidades.", ok=False, status=400)
    try:
        product = get_product(product_id)
    except (PyMongoError, RuntimeError):
        return _respond("Não foi possível consultar o produto.", ok=False, status=503)
    if not product or product.get("estoque", 0) < 1:
        return _respond("Produto indisponível no momento.", ok=False, status=400)
    previous_qty = int(current_cart().get(product_id, 0))
    available = min(MAX_QTY, int(product["estoque"]))
    if previous_qty >= available:
        return _respond("Você já adicionou a quantidade máxima disponível.", ok=False, status=400)
    set_quantity(product_id, min(previous_qty + qty, available))
    return _respond("Produto adicionado ao carrinho!")


@bp.post("/carrinho/atualizar")
def update_cart():
    product_id = request.form.get("produto_id", "")
    if product_id not in current_cart():
        return _respond("Item não encontrado no carrinho.", ok=False, status=400)
    try:
        qty = int(request.form.get("quantidade", 1))
        if qty < 0 or qty > MAX_QTY:
            raise ValueError
        if qty:
            product = get_product(product_id)
            if not product:
                raise ValueError
            qty = min(qty, int(product.get("estoque", 0)))
        set_quantity(product_id, qty)
    except (ValueError, TypeError):
        return _respond("Quantidade inválida ou produto indisponível.", ok=False, status=400)
    except (PyMongoError, RuntimeError):
        return _respond("Não foi possível atualizar o carrinho.", ok=False, status=503)
    flash("Carrinho atualizado.", "success")
    return redirect(url_for("shop.cart"))


@bp.post("/carrinho/remover")
def remove_from_cart():
    product_id = request.form.get("produto_id", "")
    set_quantity(product_id, 0)
    flash("Produto removido do carrinho.", "success")
    return redirect(url_for("shop.cart"))


@bp.route("/comprar")
def buy():
    try:
        rows, total = cart_details()
        if not rows:
            flash("Adicione produtos ao carrinho antes de comprar.", "error")
            return redirect(url_for("shop.cart"))
        link = whatsapp_link(rows, total)
    except (PyMongoError, RuntimeError, ValueError):
        flash("Não foi possível preparar o pedido. Confira a configuração dos bancos e do WhatsApp.", "error")
        return redirect(url_for("shop.cart"))
    # Não esvazia o carrinho: o WhatsApp abre uma conversa, não confirma o pagamento.
    return redirect(link)
