from flask import Blueprint, request, jsonify
import os
from supabase import create_client
from datetime import datetime

bp = Blueprint("payments", __name__, url_prefix="/api/payments")

SUPABASE = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
DEV_PAYMENTS = os.getenv("DEV_PAYMENTS", "false").lower() == "true"

def get_user_id(req):
    uid = req.headers.get("X-User-Id")
    return uid  

@bp.post("/checkout")
def checkout():
    
    if DEV_PAYMENTS:
        return jsonify({
            "dev": True,
            "message": "DEV: Stripe not configured. Use /grant-dev-credits to add credits."
        }), 200
    return jsonify({"error": "Stripe not configured"}), 501

@bp.post("/grant-dev-credits")
def grant_dev_credits():
    if not DEV_PAYMENTS:
        return jsonify({"error": "Dev payments disabled"}), 403
    uid = get_user_id(request)
    if not uid:
        return jsonify({"error": "Missing user"}), 401
    SUPABASE.table("profiles").upsert({"user_id": uid}).execute()
    SUPABASE.rpc("increment_profile_credits", {"p_user_id": uid, "p_delta": 10}).execute() \
        if "increment_profile_credits" in [f["name"] for f in SUPABASE.rpc("").functions] \
        else SUPABASE.table("profiles").update({"credits": SUPABASE.sql("credits + 10")}).eq("user_id", uid).execute()
    # record pseudo purchase
    SUPABASE.table("purchases").insert({
        "user_id": uid, "amount_cents": 500, "credits_granted": 10, "status": "DEV_GRANTED"
    }).execute()
    return jsonify({"ok": True, "granted": 10})
