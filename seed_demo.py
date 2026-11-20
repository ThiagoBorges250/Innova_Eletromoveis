"""Insere produtos fictícios para testar. Executar uma única vez: python seed_demo.py"""
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

from services.products import collection, ensure_indexes
from services.product_photos import curated_photo

PRODUCTS = [
    ("Sofá retrátil e reclinável 3 lugares", "Sofás", 189990, 8, "Sofá confortável em tecido cinza, ideal para sua sala.", "sofa.svg"),
    ("Cama casal com cabeceira estofada", "Camas", 129990, 6, "Cama casal com visual acolhedor e cabeceira elegante.", "cama.svg"),
    ("Guarda-roupas 6 portas amadeirado", "Guarda-roupas", 153590, 5, "Roupeiro espaçoso, com portas e prateleiras internas.", "armario.svg"),
    ("Mesa de jantar com 4 cadeiras", "Salas de jantar", 119990, 7, "Conjunto de jantar para quatro pessoas.", "jantar.svg"),
    ("Rack para TV e painel moderno", "Racks e painéis", 69990, 9, "Rack com compartimentos para organizar a sala.", "rack.svg"),
    ("Geladeira duplex inox", "Geladeiras", 279990, 4, "Geladeira duplex com acabamento inox.", "geladeira.svg"),
    ("Fogão 4 bocas com forno", "Fogões", 134990, 6, "Fogão prático para o dia a dia.", "fogao.svg"),
    ("Máquina de lavar 12 kg", "Máquinas de lavar", 219990, 3, "Lavadora para facilitar a rotina da casa.", "lavadora.svg"),
]

if __name__ == "__main__":
    ensure_indexes()
    col = collection()
    if col.count_documents({}) > 0:
        print("A coleção já possui produtos. Nenhum documento foi duplicado.")
    else:
        now = datetime.now(timezone.utc)
        docs = [{
            "nome": name,
            "categoria": category,
            "preco_centavos": cents,
            "estoque": stock,
            "descricao": desc + " Dados fictícios para demonstração; confirme características e preços reais antes de usar comercialmente.",
            "imagem": curated_photo(name, category) or "/static/img/" + image,
            "ativo": True,
            "destaque": i < 4,
            "criado_em": now,
            "atualizado_em": now,
        } for i, (name, category, cents, stock, desc, image) in enumerate(PRODUCTS)]
        col.insert_many(docs)
        print(f"{len(docs)} produtos de DEMONSTRAÇÃO inseridos no MongoDB!")
