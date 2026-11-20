
import os
from supabase import create_client


def configured():
    return all(os.getenv(key) for key in ("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY"))


def is_admin(user_id):
    url = os.environ["SUPABASE_URL"]
    secret = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    client = create_client(url, secret)
    response = client.table("admins").select("user_id").eq("user_id", str(user_id)).limit(1).execute()
    return bool(response.data)


def authenticate_admin(email, password):
    if not configured():
        raise RuntimeError("Supabase ainda não está configurado no .env")
    # Cliente por tentativa: impede compartilhamento de sessão Auth entre usuários.
    client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_ANON_KEY"])
    response = client.auth.sign_in_with_password({"email": email, "password": password})
    user = response.user
    if user is None or not is_admin(user.id):
        return None
    return {"id": str(user.id), "email": user.email or email}
