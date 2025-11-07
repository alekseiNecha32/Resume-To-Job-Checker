import os
import json
import stripe
from flask import Blueprint, request, jsonify, current_app
from supabase import create_client

stripe_bp = Blueprint("stripe_payments", __name__, url_prefix="/api/payments")

# env
STRIPE_SECRET = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")  # optional for webhook signature verification
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if STRIPE_SECRET:
    stripe.api_key = STRIPE_SECRET

SUPABASE = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        SUPABASE = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception:
        current_app.logger.exception("Failed to create supabase client")

# server-side pack truth (only pro + custom)
PACKS = {
    "pro": {"credits": 10, "amount_dollars": 5},
}


def _resolve_user_id(req):
    # Prefer Authorization: Bearer <token> -> supabase admin get_user if available
    auth = req.headers.get("Authorization", "") or ""
    if auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
        try:
            if SUPABASE and hasattr(SUPABASE.auth, "api") and hasattr(SUPABASE.auth.api, "get_user"):
                resp = SUPABASE.auth.api.get_user(token)
                user = (resp.get("data") or {}).get("user") if isinstance(resp, dict) else getattr(resp, "user", None)
                if user:
                    return user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
            elif SUPABASE and hasattr(SUPABASE.auth, "get_user"):
                resp = SUPABASE.auth.get_user(token)
                user = (resp.get("data") or {}).get("user") if isinstance(resp, dict) else getattr(resp, "user", None)
                if user:
                    return user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
        except Exception:
            current_app.logger.debug("supabase get_user failed", exc_info=True)
    # fallback for local/dev: X-User-Id header
    return req.headers.get("X-User-Id")


@stripe_bp.post("/checkout")
def checkout():
    """
    Create a Stripe Checkout Session.
    Body: { packId?, credits? }.
    Server enforces pricing:
      - packId == "pro" -> 10 credits for $5
      - custom -> $1 per credit (credits must be integer >=1)
    Returns: { url: "<stripe_checkout_url>" }
    """
    # If Stripe not configured, return helpful response
    if not STRIPE_SECRET:
        return jsonify({"error": "stripe_not_configured", "message": "Set STRIPE_SECRET_KEY on server"}), 501

    body = request.get_json(silent=True) or {}
    pack_id = body.get("packId")
    req_credits = body.get("credits")

    # determine credits and price server-side
    if pack_id in PACKS:
        credits = PACKS[pack_id]["credits"]
        amount_dollars = PACKS[pack_id]["amount_dollars"]
    else:
        try:
            credits = int(req_credits or 0)
        except Exception:
            return jsonify({"error": "invalid_credits"}), 400
        if credits < 1:
            return jsonify({"error": "invalid_credits"}), 400
        # pricing: $1 per credit for custom
        amount_dollars = credits * 1

    amount_cents = int(round(amount_dollars * 100))
    user_id = _resolve_user_id(request) or ""


    current_app.logger.info("checkout request: resolved user_id=%s body=%s", user_id, body)


    product_name = f"{'Custom' if pack_id not in PACKS else pack_id} — {credits} credits"
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="payment",
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {"name": product_name},
                        "unit_amount": amount_cents,
                    },
                    "quantity": 1,
                }
            ],
            metadata={"user_id": user_id, "pack_id": pack_id or "custom", "credits": str(credits)},
            success_url=f"{FRONTEND_URL}/pay/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{FRONTEND_URL}/pay/cancel",
        )
        current_app.logger.info("created stripe session id=%s url=%s", session.get("id"), session.get("url"))
        return jsonify({"url": session.get("url")}), 200
    except stripe.error.StripeError as se:
        current_app.logger.exception("Stripe error during checkout")
        return jsonify({"error": "stripe_error", "message": str(se)}), 502
    except Exception:
        current_app.logger.exception("checkout error")
        return jsonify({"error": "internal_server_error"}), 500


@stripe_bp.post("/webhook")
def webhook():
    """
    Handle Stripe webhooks. Expects checkout.session.completed events.
    Grants credits once per stripe_session_id (idempotent).
    """
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")
    event = None


    # debug: log raw payload (trimmed) and signature header
    try:
       current_app.logger.debug("Stripe webhook raw payload (trim): %s", (payload.decode("utf-8", "replace")[:2000] if payload else ""))
    except Exception:
       current_app.logger.debug("Stripe webhook raw payload (binary) present")
    current_app.logger.debug("Stripe-Signature header: %s", sig_header)

    try:
        if STRIPE_WEBHOOK_SECRET and sig_header:
            event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
        else:
            event = json.loads(payload)
    except Exception:
        current_app.logger.exception("Webhook signature verification failed")
        return jsonify({"error": "invalid_webhook"}), 400

    if event.get("type") == "checkout.session.completed":
        session = event["data"]["object"]

        current_app.logger.info(
            "checkout.session.completed received: id=%s, payment_status=%s, amount_total=%s, metadata=%s",
            session.get("id"),
            session.get("payment_status") or session.get("status"),
            session.get("amount_total"),
            session.get("metadata"),
           )
        # ensure payment is completed
        payment_status = session.get("payment_status") or session.get("status")
        if payment_status != "paid":
            current_app.logger.info("Checkout session not paid yet, skipping: %s", session.get("id"))
            return jsonify({"received": True}), 200

        stripe_session_id = session.get("id")
        # check idempotency: has this session already been recorded?
        try:
            already = None
            if SUPABASE:
                res = SUPABASE.table("purchases").select("id").eq("stripe_session_id", stripe_session_id).limit(1).execute()
                # adapt to supabase client result shape
                already_rows = getattr(res, "data", None) or (res.get("data") if isinstance(res, dict) else None)
                if already_rows:
                    current_app.logger.info("Purchase already recorded for session %s, skipping", stripe_session_id)
                    return jsonify({"received": True}), 200
        except Exception:
            current_app.logger.exception("Failed to check existing purchase; continuing")

        metadata = session.get("metadata", {}) or {}
        uid = metadata.get("user_id")
        try:
            credits = int(metadata.get("credits", "0") or 0)
        except Exception:
            credits = 0
        amount_total = int(session.get("amount_total") or 0)

        try:
            if SUPABASE and uid:
                # ensure profile exists
                SUPABASE.table("profiles").upsert({"user_id": uid}).execute()
                # preferred: use RPC to increment credits
                try:
                    SUPABASE.rpc("increment_profile_credits", {"p_user_id": uid, "p_delta": credits}).execute()
                    current_app.logger.info("Incremented %s credits for user %s via RPC", credits, uid)
                except Exception:
                    # fallback: read-update
                    cur = SUPABASE.table("profiles").select("credits").eq("user_id", uid).single().execute()
                    current_credits = 0
                    if hasattr(cur, "data"):
                        current_credits = int((cur.data or {}).get("credits") or 0)
                    else:
                        current_credits = int((cur.get("data") or {}).get("credits") or 0)
                    SUPABASE.table("profiles").update({"credits": current_credits + credits}).eq("user_id", uid).execute()
                    current_app.logger.info("Updated user %s credits from %s to %s (fallback)", uid, current_credits, current_credits + credits)


                # insert purchase record (mark completed)
                SUPABASE.table("purchases").insert({
                    "user_id": uid,
                    "amount_cents": amount_total,
                    "credits_granted": credits,
                    "status": "COMPLETED",
                    "stripe_session_id": stripe_session_id,
                }).execute()
                current_app.logger.info("Inserted purchase record for session %s user %s credits %s", stripe_session_id, uid, credits)
        except Exception:
            current_app.logger.exception("failed to persist purchase")

    return jsonify({"received": True}), 200