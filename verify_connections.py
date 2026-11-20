"""Executar: python verify_connections.py"""
from dotenv import load_dotenv
load_dotenv()

from services.db import get_database, get_redis
from services.auth import configured


def check(name, fn):
    try:
        fn()
        print(f"[OK] {name}")
    except Exception as exc:
        print(f"[ERRO] {name}: {type(exc).__name__} — confira o .env e a rede")


if __name__ == "__main__":
    check("MongoDB", lambda: get_database().command("ping"))
    check("Redis", lambda: get_redis().ping() or (_ for _ in ()).throw(RuntimeError("sem resposta")))
    print("[OK] Supabase: variáveis presentes" if configured() else "[ERRO] Supabase: variáveis ausentes")
    print("Dica: login só funciona após criar usuário Auth e registrá-lo em public.admins.")
