from flask import Blueprint, request, jsonify
from supabase import create_client
import os
from dotenv import load_dotenv

auth_bp = Blueprint("auth_api", __name__, url_prefix="/api")

# ...existing code...
# ...existing code...
# ...existing code...
@auth_bp.get("/me")
def me():
    """Return current user id / credits. Accepts X-User-Id (dev) or Authorization: Bearer <token>."""
    try:
        headers = dict(request.headers)
        print("DEBUG: incoming headers:", headers)

        load_dotenv()
        SUPABASE_URL = os.getenv("SUPABASE_URL")
        SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        print("DEBUG: SUPABASE_URL:", bool(SUPABASE_URL), "SUPABASE_KEY:", bool(SUPABASE_KEY))

        if not SUPABASE_URL or not SUPABASE_KEY:
            print("DEBUG: missing SUPABASE env")
            return jsonify({"error": "server_misconfigured"}), 500

        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

        # Dev override header
        dev_uid = request.headers.get("X-User-Id")
        if dev_uid:
            print("DEBUG: using X-User-Id override:", dev_uid)
            profile_res = supabase.table("profiles").select("credits").eq("user_id", dev_uid).execute()
            # normalize result shapes
            pdata_raw = profile_res.get("data") if isinstance(profile_res, dict) else getattr(profile_res, "data", None)
            if isinstance(pdata_raw, list):
                pdata = pdata_raw[0] if pdata_raw else {}
            elif isinstance(pdata_raw, dict):
                pdata = pdata_raw
            else:
                pdata = {}
            return jsonify({"user_id": dev_uid, "credits": pdata.get("credits", 0), "email": None}), 200

        auth = request.headers.get("Authorization", "") or ""
        if os.getenv("DEBUG_AUTH_ECHO", "0") == "1":
            return jsonify({"headers": headers}), 200

        if not auth.lower().startswith("bearer "):
            print("DEBUG: no Bearer token present")
            return jsonify({"error": "unauthorized"}), 401

        token = auth.split(" ", 1)[1].strip()
        print("DEBUG: token prefix:", token[:40])

        user = None
        # Try auth.api.get_user then auth.get_user (handle different SDK shapes)
        try:
            if hasattr(supabase.auth, "api") and hasattr(supabase.auth.api, "get_user"):
                print("DEBUG: calling supabase.auth.api.get_user")
                uresp = supabase.auth.api.get_user(token)
                print("DEBUG: auth.api.get_user raw ->", repr(uresp))
                user = (uresp.get("data") or {}).get("user") if isinstance(uresp, dict) else getattr(uresp, "user", None)
            elif hasattr(supabase.auth, "get_user"):
                print("DEBUG: calling supabase.auth.get_user")
                uresp2 = supabase.auth.get_user(token)
                print("DEBUG: auth.get_user raw ->", repr(uresp2))
                user = (uresp2.get("data") or {}).get("user") if isinstance(uresp2, dict) else getattr(uresp2, "user", None)
        except Exception as e:
            print("DEBUG: get_user exception:", repr(e))
            user = None

        if not user:
            print("DEBUG: user not resolved from token -- token may be invalid/expired or wrong project")
            return jsonify({"error": "unauthorized"}), 401

        # extract id/email safely for both dict and object shapes
        if isinstance(user, dict):
            uid = user.get("id")
            email = user.get("email")
        else:
            uid = getattr(user, "id", None)
            email = getattr(user, "email", None)

        if not uid:
            print("DEBUG: resolved user has no id:", user)
            return jsonify({"error": "unauthorized"}), 401

        print("DEBUG: resolved user id:", uid)

        # fetch profile without .single() and handle missing row
        profile_res = supabase.table("profiles").select("credits").eq("user_id", uid).execute()
        pdata_raw = profile_res.get("data") if isinstance(profile_res, dict) else getattr(profile_res, "data", None)
        if isinstance(pdata_raw, list):
            pdata = pdata_raw[0] if pdata_raw else {}
        elif isinstance(pdata_raw, dict):
            pdata = pdata_raw
        else:
            pdata = {}

        credits = pdata.get("credits", 0)
        return jsonify({"user_id": uid, "credits": credits, "email": email}), 200

    except Exception as exc:
        import traceback
        print("UNCAUGHT /me exception:")
        traceback.print_exc()
        return jsonify({"error": "internal_server_error"}), 500
# ...existing code...