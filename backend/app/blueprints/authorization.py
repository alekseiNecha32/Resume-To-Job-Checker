from flask import Blueprint, request, jsonify
from supabase import create_client
import os
from dotenv import load_dotenv

auth_bp = Blueprint("auth_api", __name__, url_prefix="/api")

@auth_bp.get("/me")
def me():
    """Return current user id / credits. Accepts X-User-Id (dev) or Authorization: Bearer <token>."""
    print("DEBUG: Authorization header:", request.headers.get("Authorization"))

    load_dotenv()
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not SUPABASE_URL or not SUPABASE_KEY:
        return jsonify({"error": "server_misconfigured"}), 500

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Dev override header
    uid = request.headers.get("X-User-Id")
    if uid:
        profile = supabase.table("profiles").select("credits,email,full_name").eq("user_id", uid).single().execute()
        p = profile.data or {}
        return jsonify({"user_id": uid, "credits": p.get("credits", 0), "email": p.get("email")}), 200

    auth = request.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        return jsonify({"error": "unauthorized"}), 401

    token = auth.split(" ", 1)[1].strip()
    user = None
    # support different supabase-python shapes
    try:
        uresp = supabase.auth.get_user(token)
        user = getattr(uresp, "user", None) or (uresp.get("data") or {}).get("user") if isinstance(uresp, dict) else None
    except Exception:
        try:
            uresp = supabase.auth.api.get_user(token)
            user = (uresp.get("data") or {}).get("user") if isinstance(uresp, dict) else None
        except Exception:
            user = None

    if not user:
        return jsonify({"error": "unauthorized"}), 401

    uid = user.get("id")
    profile = supabase.table("profiles").select("credits,email,full_name").eq("user_id", uid).single().execute()
    p = profile.data or {}
    return jsonify({"user_id": uid, "credits": p.get("credits", 0), "email": p.get("email")}), 200