"""Carrinho na sessão Flask; dados e preços revalidados no MongoDB."""
import os
from urllib.parse import quote
from flask import session

from services.products import format_brl, get_products_by_ids

MAX_QTY = 20


def current_cart():
    data = session.get("cart", {})
    return dict(data) if isinstance(data, dict) else {}


def set_quantity(product_id, qty):
    cart = current_cart()
    if qty <= 0:
        cart.pop(str(product_id), None)
    else:
        cart[str(product_id)] = min(int(qty), MAX_QTY)
    session["cart"] = cart
    session.modified = True


def cart_details():
    cart = current_cart()
    items_by_id = get_products_by_ids(cart.keys())
    rows = []
    total = 0
    for pid, raw_qty in cart.items():
        product = items_by_id.get(pid)
        if not product:
            continue
        qty = min(max(0, int(raw_qty)), MAX_QTY, max(0, int(product.get("estoque", 0))))
        if qty <= 0:
            continue
        subtotal = qty * int(product["preco_centavos"])
        total += subtotal
        rows.append({"produto": product, "quantidade": qty, "subtotal": subtotal})
    return rows, total


def whatsapp_message(rows, total):
    """Monta a mensagem usando preços e quantidades revalidados no MongoDB.

    O link abre a conversa: o cliente confirma o envio no WhatsApp.
    """
    if not rows:
        raise ValueError("Não há produtos no carrinho para finalizar o pedido.")

    lines = [
        "Olá! Gostaria de realizar este pedido na *Innova EletroMóveis*.",
        "",
        "*PRODUTOS DO CARRINHO*",
        "",
    ]
    calculated_total = 0

    for index, row in enumerate(rows, start=1):
        product = row["produto"]
        qty = int(row["quantidade"])
        unit_price = int(product["preco_centavos"])
        if qty < 1 or unit_price < 1:
            raise ValueError("Produto ou quantidade inválidos no carrinho.")

        subtotal = qty * unit_price
        calculated_total += subtotal
        # Impede que nomes com quebras de linha desconfigurem o pedido.
        name = " ".join(str(product.get("nome") or "Produto").split()).replace("*", "")
        lines.extend([
            f"{index}. *{name}*",
            f"   Quantidade: {qty}",
            f"   Preço unitário: {format_brl(unit_price)}",
            f"   Subtotal: {format_brl(subtotal)}",
            "",
        ])

    if calculated_total != int(total):
        raise ValueError("O total do carrinho está inconsistente. Atualize e tente novamente.")

    lines.extend([
        "*VALOR TOTAL DA COMPRA*",
        f"Total: {format_brl(total)}",
        "",
        "Podem confirmar a disponibilidade e as informações sobre entrega?",
    ])
    return "\n".join(lines)


def whatsapp_link(rows, total):
    """Cria link wa.me com a mensagem completa, codificada para a URL."""
    number = "".join(c for c in os.getenv("WHATSAPP_NUMBER", "5589981342222") if c.isdigit())
    if not 10 <= len(number) <= 15:
        raise ValueError("Configure WHATSAPP_NUMBER em formato internacional no .env")
    message = whatsapp_message(rows, total)
    return f"https://wa.me/{number}?text={quote(message, safe='')}"
