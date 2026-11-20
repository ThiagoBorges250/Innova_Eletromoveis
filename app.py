"""Innova Eletromóveis — Flask + Supabase Auth + MongoDB + Redis."""
import os
from datetime import timedelta

from dotenv import load_dotenv
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from flask_wtf.csrf import CSRFProtect, CSRFError
from pymongo.errors import PyMongoError

from services.products import CATEGORIES, format_brl

load_dotenv()
csrf = CSRFProtect()


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.getenv("FLASK_SECRET_KEY", ""),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("FLASK_COOKIE_SECURE", "0") == "1",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,
        WTF_CSRF_TIME_LIMIT=8 * 60 * 60,
    )
    if test_config:
        app.config.update(test_config)
    if not app.config["SECRET_KEY"] or app.config["SECRET_KEY"].startswith("SUBSTITUA"):
        raise RuntimeError(
            "Configure FLASK_SECRET_KEY no arquivo .env. "
            'Gere com: python -c "import secrets; print(secrets.token_hex(32))"'
        )

    csrf.init_app(app)
    app.jinja_env.filters["brl"] = format_brl

    from routes.admin import bp as admin_bp
    from routes.shop import bp as shop_bp

    app.register_blueprint(shop_bp)
    app.register_blueprint(admin_bp)

    @app.context_processor
    def template_globals():
        cart = session.get("cart", {})
        count = sum(int(qty) for qty in cart.values()) if isinstance(cart, dict) else 0
        number = "".join(c for c in os.getenv("WHATSAPP_NUMBER", "5589981342222") if c.isdigit())
        return {
            "whatsapp_contact_url": f"https://wa.me/{number}" if 10 <= len(number) <= 15 else "#",
            "whatsapp_display": os.getenv("WHATSAPP_DISPLAY", "(89) 98134-2222"),
            "cart_count": count,
            "categories": CATEGORIES,
            "admin_logged_in": bool(session.get("admin_id")),
        }

    @app.route("/saude")
    def health():
        """Diagnóstico simples, sem revelar credenciais."""
        from services.db import get_database, get_redis
        states = {}
        try:
            get_database().command("ping")
            states["mongodb"] = "ok"
        except Exception:
            states["mongodb"] = "indisponivel"
        try:
            get_redis().ping()
            states["redis"] = "ok"
        except Exception:
            states["redis"] = "indisponivel"
        states["supabase"] = "configurado" if os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_ANON_KEY") and os.getenv("SUPABASE_SERVICE_ROLE_KEY") else "nao_configurado"
        return jsonify(states)

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify(error="A sessão expirou. Atualize a página e tente novamente."), 400
        flash("Sua sessão expirou. Atualize a página e tente novamente.", "error")
        return redirect(url_for("shop.index"))

    @app.errorhandler(404)
    def not_found(error):
        return render_template("error.html", code=404, message="Página não encontrada."), 404

    @app.errorhandler(413)
    def too_large(error):
        flash("Imagem muito grande: o limite é 5 MB.", "error")
        return redirect(url_for("admin.dashboard") if session.get("admin_id") else url_for("shop.index"))

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=os.getenv("FLASK_DEBUG", "0") == "1")
