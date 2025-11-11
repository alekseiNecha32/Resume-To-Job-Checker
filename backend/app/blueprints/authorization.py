from flask import Blueprint, request, jsonify
from supabase import create_client
import os
from dotenv import load_dotenv

auth_bp = Blueprint("auth_api", __name__, url_prefix="/api")

def _profiles_has_full_name(supabase_client):
    """Best-effort detection of full_name column. Cache result on function attribute."""
    if hasattr(_profiles_has_full_name, "_cache"):
        return getattr(_profiles_has_full_name, "_cache")
    try:
        # Try selecting one row including full_name; if column missing PostgREST returns error
        probe = supabase_client.table("profiles").select("full_name").limit(1).execute()
        # If no exception / error attribute, assume exists
        _profiles_has_full_name._cache = True  # type: ignore
    except Exception:
        _profiles_has_full_name._cache = False  # type: ignore
    return getattr(_profiles_has_full_name, "_cache")


@auth_bp.post("/auth/create_profile")
def create_profile():
    """Upsert a profile for the authenticated user with starter credits (10)."""
    try:
        load_dotenv()
        SUPABASE_URL = os.getenv("SUPABASE_URL")
        SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not SUPABASE_URL or not SUPABASE_KEY:
            return jsonify({"error": "server_misconfigured"}), 500

        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

        auth = request.headers.get("Authorization", "") or ""
        if not auth.lower().startswith("bearer "):
            return jsonify({"error": "unauthorized"}), 401

        token = auth.split(" ", 1)[1].strip()

        user = None
        try:
            if hasattr(supabase.auth, "api") and hasattr(supabase.auth.api, "get_user"):
                uresp = supabase.auth.api.get_user(token)
                user = (uresp.get("data") or {}).get("user") if isinstance(uresp, dict) else getattr(uresp, "user", None)
            elif hasattr(supabase.auth, "get_user"):
                uresp2 = supabase.auth.get_user(token)
                user = (uresp2.get("data") or {}).get("user") if isinstance(uresp2, dict) else getattr(uresp2, "user", None)
        except Exception as e:
            print("DEBUG create_profile get_user exception:", repr(e))
            return jsonify({"error": "unauthorized"}), 401

        if not user:
            return jsonify({"error": "unauthorized"}), 401

        uid = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
        email = user.get("email") if isinstance(user, dict) else getattr(user, "email", None)

        if not uid:
            return jsonify({"error": "unauthorized"}), 401

        body = request.get_json(silent=True) or {}
        full_name = body.get("full_name") or (user.get("user_metadata", {}) or {}).get("full_name") if isinstance(user, dict) else None

        # upsert profile with starter credits
        # use upsert so it creates or updates existing row
        payload = {"user_id": uid, "email": email, "credits": 10}
        if full_name and _profiles_has_full_name(supabase):
            payload["full_name"] = full_name
        try:
            supabase.table("profiles").upsert(payload).execute()
        except TypeError:
            # older client variant
            supabase.table("profiles").upsert(payload, on_conflict="user_id").execute()

        return jsonify({"user_id": uid, "email": email, "credits": 10}), 200

    except Exception:
        import traceback
        traceback.print_exc()
        return jsonify({"error": "internal_server_error"}), 500





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

        # fetch profile; include full_name only if column present
        select_cols = "credits, full_name" if _profiles_has_full_name(supabase) else "credits"
        try:
            profile_res = supabase.table("profiles").select(select_cols).eq("user_id", uid).execute()
        except Exception:
            # fallback to credits only
            profile_res = supabase.table("profiles").select("credits").eq("user_id", uid).execute()
        pdata_raw = profile_res.get("data") if isinstance(profile_res, dict) else getattr(profile_res, "data", None)
        if isinstance(pdata_raw, list):
            pdata = pdata_raw[0] if pdata_raw else {}
        elif isinstance(pdata_raw, dict):
            pdata = pdata_raw
        else:
            pdata = {}

        credits = pdata.get("credits", 0)
        full_name = pdata.get("full_name") if _profiles_has_full_name(supabase) else None
        return jsonify({"user_id": uid, "credits": credits, "email": email, "full_name": full_name}), 200

    except Exception as exc:
        import traceback
        print("UNCAUGHT /me exception:")
        traceback.print_exc()
        return jsonify({"error": "internal_server_error"}), 500
@auth_bp.post("/profile")
def update_profile():
    """Update editable profile fields for the authenticated user.
    Currently supports: full_name.
    """
    try:
        load_dotenv()
        SUPABASE_URL = os.getenv("SUPABASE_URL")
        SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not SUPABASE_URL or not SUPABASE_KEY:
            return jsonify({"error": "server_misconfigured"}), 500

        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

        auth = request.headers.get("Authorization", "") or ""
        if not auth.lower().startswith("bearer "):
            return jsonify({"error": "unauthorized"}), 401
        token = auth.split(" ", 1)[1].strip()

        # Resolve user from token
        user = None
        try:
            if hasattr(supabase.auth, "api") and hasattr(supabase.auth.api, "get_user"):
                uresp = supabase.auth.api.get_user(token)
                user = (uresp.get("data") or {}).get("user") if isinstance(uresp, dict) else getattr(uresp, "user", None)
            elif hasattr(supabase.auth, "get_user"):
                uresp2 = supabase.auth.get_user(token)
                user = (uresp2.get("data") or {}).get("user") if isinstance(uresp2, dict) else getattr(uresp2, "user", None)
        except Exception:
            user = None

        if not user:
            return jsonify({"error": "unauthorized"}), 401

        uid = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
        email = user.get("email") if isinstance(user, dict) else getattr(user, "email", None)
        if not uid:
            return jsonify({"error": "unauthorized"}), 401

        body = request.get_json(silent=True) or {}
        full_name = body.get("full_name")

        update = {"user_id": uid}
        want_full = isinstance(full_name, str) and full_name.strip()
        has_full = _profiles_has_full_name(supabase)
        if want_full and has_full:
            update["full_name"] = full_name.strip()

        # Upsert so row exists even if missing
        try:
            supabase.table("profiles").upsert(update, on_conflict="user_id").execute()
        except TypeError:
            supabase.table("profiles").upsert(update).execute()
        except Exception:
            # If full_name caused the error, retry without it
            if "full_name" in update:
                update_no_full = {k: v for k, v in update.items() if k != "full_name"}
                try:
                    supabase.table("profiles").upsert(update_no_full).execute()
                except Exception:
                    pass

        # Read back profile
        select_cols = "credits, full_name" if _profiles_has_full_name(supabase) else "credits"
        try:
            prof = supabase.table("profiles").select(select_cols).eq("user_id", uid).execute()
        except Exception:
            prof = supabase.table("profiles").select("credits").eq("user_id", uid).execute()
        pdata_raw = prof.get("data") if isinstance(prof, dict) else getattr(prof, "data", None)
        if isinstance(pdata_raw, list):
            pdata = pdata_raw[0] if pdata_raw else {}
        elif isinstance(pdata_raw, dict):
            pdata = pdata_raw
        else:
            pdata = {}

        return jsonify({
            "user_id": uid,
            "email": email,
            "credits": pdata.get("credits", 0),
            "full_name": pdata.get("full_name") if _profiles_has_full_name(supabase) else None
        }), 200

    except Exception:
        import traceback
        traceback.print_exc()
        return jsonify({"error": "internal_server_error"}), 500