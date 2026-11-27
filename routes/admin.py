"""Admin restrito com login Supabase e autorização na tabela public.admins."""
from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from pymongo.errors import PyMongoError

from services.auth import authenticate_admin, is_admin
from services.images import remove_product_image, save_product_image
from services.products import (
    create_product, delete_product, get_product, list_products, update_product,
    validate_product_form,
)
from services.vector_sync import notify_n8n

bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(view):
    @wraps(view)
    def protected(*args, **kwargs):
        user_id = session.get("admin_id")
        if not user_id:
            flash("Entre como administrador para continuar.", "error")
            return redirect(url_for("admin.login"))
        try:
            # Autorização conferida de novo, para permitir revogar um administrador.
            if not is_admin(user_id):
                session.pop("admin_id", None)
                session.pop("admin_email", None)
                flash("Seu acesso administrativo foi revogado.", "error")
                return redirect(url_for("admin.login"))
        except Exception:
            return render_template("error.html", code=503,
                                   message="Não foi possível verificar a permissão no Supabase."), 503
        return view(*args, **kwargs)
    return protected


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("senha") or ""
        if not email or not password or len(email) > 254:
            flash("Informe e-mail e senha.", "error")
        else:
            try:
                admin = authenticate_admin(email, password)
                if admin:
                    session.clear()
                    session.permanent = True
                    session["admin_id"] = admin["id"]
                    session["admin_email"] = admin["email"]
                    flash("Login realizado com sucesso!", "success")
                    return redirect(url_for("admin.dashboard"))
            except Exception:
                # Não informar se o e-mail existe, se a senha falhou ou se não é admin.
                pass
            flash("Acesso negado. Verifique credenciais, permissão e configuração do Supabase.", "error")
    return render_template("login.html")


@bp.post("/sair")
def logout():
    session.clear()
    flash("Você saiu do painel.", "success")
    return redirect(url_for("shop.index"))


@bp.route("/")
@admin_required
def dashboard():
    try:
        produtos = list_products(admin=True, limit=200)
        error = False
    except (PyMongoError, RuntimeError):
        produtos, error = [], True
    return render_template("admin.html", produtos=produtos, mongo_error=error)


@bp.route("/produtos/novo", methods=["GET", "POST"])
@admin_required
def new_product():
    if request.method == "POST":
        image_url = None
        try:
            data = validate_product_form(request.form)
            image_url = save_product_image(request.files.get("imagem"))
            data["imagem"] = image_url or "/static/img/sem-foto.svg"
            product_id = create_product(data)
            notify_n8n(product_id)
            flash("Produto cadastrado no MongoDB! Já aparece no catálogo.", "success")
            return redirect(url_for("admin.dashboard"))
        except (ValueError, PyMongoError, RuntimeError) as exc:
            if image_url:
                remove_product_image(image_url)
            flash(f"Não foi possível cadastrar: {exc if isinstance(exc, ValueError) else 'falha de conexão com MongoDB.'}", "error")
    return render_template("product_form.html", produto=None, title="Novo produto")


@bp.route("/produtos/<product_id>/editar", methods=["GET", "POST"])
@admin_required
def edit_product(product_id):
    try:
        produto = get_product(product_id, admin=True)
    except (PyMongoError, RuntimeError):
        return render_template("error.html", code=503, message="MongoDB indisponível."), 503
    if not produto:
        return render_template("error.html", code=404, message="Produto não encontrado."), 404
    if request.method == "POST":
        new_image = None
        try:
            data = validate_product_form(request.form)
            new_image = save_product_image(request.files.get("imagem"))
            if new_image:
                data["imagem"] = new_image
            if update_product(product_id, data):
                notify_n8n(product_id)
                if new_image:
                    remove_product_image(produto.get("imagem"))
                flash("Produto atualizado no MongoDB!", "success")
                return redirect(url_for("admin.dashboard"))
            raise ValueError("Produto não encontrado para atualização.")
        except (ValueError, PyMongoError, RuntimeError) as exc:
            if new_image:
                remove_product_image(new_image)
            flash(f"Não foi possível atualizar: {exc if isinstance(exc, ValueError) else 'falha de conexão com MongoDB.'}", "error")
    return render_template("product_form.html", produto=produto, title="Editar produto")


@bp.post("/produtos/<product_id>/excluir")
@admin_required
def remove_product(product_id):
    try:
        produto = get_product(product_id, admin=True)
        if produto and delete_product(product_id):
            notify_n8n(product_id)
            remove_product_image(produto.get("imagem"))
            flash("Produto excluído do MongoDB.", "success")
        else:
            flash("Produto não encontrado.", "error")
    except (PyMongoError, RuntimeError):
        flash("Não foi possível excluir o produto.", "error")
    return redirect(url_for("admin.dashboard"))
