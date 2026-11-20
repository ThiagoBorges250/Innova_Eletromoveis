"""Atualiza APENAS a imagem dos oito produtos conhecidos no MongoDB.

Uso (na pasta do projeto, com .env configurado):
    python aplicar_fotos_produtos.py

Não cria produtos, não altera nome, preço, estoque, categoria ou destaque.
Não substitui fotografias personalizadas de produtos sem --substituir-personalizadas.
"""
import argparse
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

from services.products import collection
from services.product_photos import PHOTOS, curated_photo, _normalize


def update_photos(col, *, replace_custom=False):
    eligible = {( _normalize(name), _normalize(category)): (new, old)
                for name, category, new, old in PHOTOS}
    current_docs = col.find({"categoria": {"$in": [item[1] for item in PHOTOS]}})
    updated = 0
    skipped = 0
    matched = set()
    for doc in current_docs:
        key = (_normalize(doc.get('nome')), _normalize(doc.get('categoria')))
        pair = eligible.get(key)
        if pair is None:
            continue
        matched.add(key)
        new, old = pair
        original = doc.get('imagem')
        if original == new:
            print(f"[OK] Foto atualizada anteriormente: {doc['nome']}")
            continue
        if (original and original not in (old, '/static/img/sem-foto.svg')
                and not replace_custom):
            print(f"[PULADO] Foto personalizada mantida: {doc['nome']}")
            skipped += 1
            continue
        col.update_one({"_id": doc["_id"]}, {"$set": {
            "imagem": new,
            "atualizado_em": datetime.now(timezone.utc),
        }})
        updated += 1
        print(f"[OK] Foto vinculada: {doc['nome']}")
    print(f"\nConcluído: {updated} registros atualizados; {skipped} preservados.")
    missing = [n for n, c, _, _ in PHOTOS if (_normalize(n), _normalize(c)) not in matched]
    if missing:
        print("Produtos ainda não encontrados no banco (não foram criados):")
        for name in missing:
            print(" -", name)
    return updated, skipped, missing


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Fotos reais da Innova no MongoDB')
    parser.add_argument('--substituir-personalizadas', action='store_true',
                        help='Também substitui foto de produto que já tenha imagem personalizada')
    args = parser.parse_args()
    try:
        update_photos(collection(), replace_custom=args.substituir_personalizadas)
    except Exception as exc:
        print(f"[ERRO] Não foi possível acessar o MongoDB: {type(exc).__name__}")
        print("Confira MONGODB_URI, IP autorizado e status do cluster no Atlas.")
        raise SystemExit(1)
