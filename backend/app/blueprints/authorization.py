import os, time, mimetypes, traceback
from flask import Blueprint, request, jsonify, make_response, Response
import json
from supabase import create_client
from dotenv import load_dotenv
import logging
logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth_api", __name__, url_prefix="/api")

def _get_supabase():
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return None
    return create_client(url, key)
def _bearer_token():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[len("Bearer "):]
    return None
def _resolve_user(supabase, token):
    user = None
    try:
        if hasattr(supabase.auth, "api") and hasattr(supabase.auth.api, "get_user"):
            resp = supabase.auth.api.get_user(token)
            user = (resp.get("data") or {}).get("user") if isinstance(resp, dict) else getattr(resp, "user", None)
        elif hasattr(supabase.auth, "get_user"):
            resp2 = supabase.auth.get_user(token)
            user = (resp2.get("data") or {}).get("user") if isinstance(resp2, dict) else getattr(resp2, "user", None)
    except Exception:
        user = None
    if not user:
        return None, None, None
    if isinstance(user, dict):
        return user.get("id"), user.get("email"), user.get("user_metadata") or {}
    return getattr(user, "id", None), getattr(user, "email", None), getattr(user, "user_metadata", {}) or {}

@auth_bp.post("/auth/create_profile")
def create_profile():
    """Create profile once after signup with starter credits (no full_name)."""
    try:
        supabase = _get_supabase()
        if not supabase:
            return jsonify({"error": "server_misconfigured"}), 500

        auth = request.headers.get("Authorization", "")
        if not auth.lower().startswith("bearer "):
            return jsonify({"error": "unauthorized"}), 401
        token = auth.split(" ", 1)[1].strip()

        uid, email, _meta = _resolve_user(supabase, token)
        if not uid:
            return jsonify({"error": "unauthorized"}), 401

        existing = supabase.table("profiles").select("user_id").eq("user_id", uid).limit(1).execute()
        raw = existing.get("data") if isinstance(existing, dict) else getattr(existing, "data", None)
        if isinstance(raw, list) and raw:
            return jsonify({"error": "profile_exists"}), 409

        row = {"user_id": uid, "email": email, "credits": 10, "avatar_url": None}
        try:
            supabase.table("profiles").upsert(row, on_conflict="user_id").execute()
        except TypeError:
            supabase.table("profiles").upsert(row).execute()

        return jsonify({"user_id": uid, "email": email, "credits": 10, "avatar_url": None}), 200
    except Exception:
        traceback.print_exc()
        return jsonify({"error": "internal_server_error"}), 500

@auth_bp.get("/me")
def me():
    token = _bearer_token()

    """Return current user id, email, credits, avatar_url."""
    try:
        supabase = _get_supabase()
        if not supabase:
            return jsonify({"error": "server_misconfigured"}), 500

        auth = request.headers.get("Authorization", "")
        if not auth.lower().startswith("bearer "):
            return jsonify({"error": "unauthorized"}), 401
        token = auth.split(" ", 1)[1].strip()

        uid, email, _meta = _resolve_user(supabase, token)
        if not uid:
            return jsonify({"error": "unauthorized"}), 401

        res = supabase.table("profiles").select("credits, avatar_url").eq("user_id", uid).limit(1).execute()
        raw = res.get("data") if isinstance(res, dict) else getattr(res, "data", None)
        row = raw[0] if isinstance(raw, list) and raw else {}

        return jsonify({
            "user_id": uid,
            "email": email,
            "credits": row.get("credits", 0),
            "avatar_url": row.get("avatar_url")
        }), 200
    except Exception:
        traceback.print_exc()
        return jsonify({"error": "internal_server_error"}), 500

@auth_bp.post("/profile")
def update_profile():
    """Upload/replace avatar. multipart/form-data field 'avatar'."""
    try:
        supabase = _get_supabase()
        if not supabase:
            return jsonify({"error": "server_misconfigured"}), 500

        auth = request.headers.get("Authorization", "")
        if not auth.lower().startswith("bearer "):
            return jsonify({"error": "unauthorized"}), 401
        token = auth.split(" ", 1)[1].strip()

        uid, email, _meta = _resolve_user(supabase, token)
        if not uid:
            return jsonify({"error": "unauthorized"}), 401

        if not (request.content_type and "multipart/form-data" in request.content_type.lower()):
            return jsonify({"error": "expected_multipart"}), 400

        avatar_file = request.files.get("avatar")
        if not avatar_file:
            return jsonify({"error": "no_file"}), 400

        bucket = os.getenv("SUPABASE_AVATAR_BUCKET", "avatars")
        try:
            supabase.storage.create_bucket(bucket, {"public": False})
        except Exception:
            pass

        ext = os.path.splitext(avatar_file.filename or "")[1].lower() or ".bin"
        mime = mimetypes.guess_type(avatar_file.filename or "")[0] or "application/octet-stream"
        path = f"{uid}/{int(time.time())}{ext}"
        data = avatar_file.read()
        
        try:
            supabase.storage.from_(bucket).upload(path, data, {"content-type": mime})
        except Exception as e:
            logger.error(f"Storage upload failed: {e}")
            return jsonify({"error": f"upload_failed: {str(e)}"}), 500

        # Get signed URL
        try:
            signed = supabase.storage.from_(bucket).create_signed_url(path, 60 * 60 * 24 * 30)
            if isinstance(signed, dict):
                avatar_url = (
                    signed.get("signedURL")
                    or signed.get("signedUrl")
                    or signed.get("signed_url")
                    or (isinstance(signed.get("data"), dict) and (
                        signed["data"].get("signedURL") or signed["data"].get("signedUrl") or signed["data"].get("signed_url")
                    ))
                )
            else:
                avatar_url = str(signed) if signed else ""
            
            if not avatar_url:
                logger.error("No signed URL returned")
                return jsonify({"error": "signed_url_failed"}), 500
        except Exception as e:
            logger.error(f"Signed URL failed: {e}")
            return jsonify({"error": f"signed_url_error: {str(e)}"}), 500

        # Update database
        update = {"user_id": uid, "avatar_url": avatar_url}
        try:
            supabase.table("profiles").upsert(update, on_conflict="user_id").execute()
        except TypeError:
            supabase.table("profiles").upsert(update).execute()
        except Exception as e:
            logger.error(f"Profile update failed: {e}")
            return jsonify({"error": f"db_update_failed: {str(e)}"}), 500

        # Fetch updated profile
        try:
            sel = supabase.table("profiles").select("credits, avatar_url").eq("user_id", uid).limit(1).execute()
            raw = sel.get("data") if isinstance(sel, dict) else getattr(sel, "data", None)
            row = raw[0] if isinstance(raw, list) and raw else {}
        except Exception as e:
            logger.error(f"Profile fetch failed: {e}")
            row = {}

        response = {
            "user_id": uid,
            "email": email,
            "credits": row.get("credits", 0),
            "avatar_url": row.get("avatar_url", avatar_url),
        }
        payload = json.dumps(response)
        resp = Response(response=payload, status=200, mimetype="application/json")
        resp.headers["Content-Type"] = "application/json; charset=utf-8"
        resp.headers["Content-Length"] = str(len(payload))
        return resp  # ✅ IMPORTANT: return the response

    except Exception as e:
        logger.error(f"update_profile error: {e}", exc_info=True)
        err_payload = json.dumps({"error": f"internal_error: {str(e)}"})
        err_resp = Response(response=err_payload, status=500, mimetype="application/json")
        err_resp.headers["Content-Type"] = "application/json; charset=utf-8"
        err_resp.headers["Content-Length"] = str(len(err_payload))
        return err_resp