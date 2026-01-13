import os
import json
import stripe
from flask import Blueprint, request, jsonify, current_app
from supabase import create_client
from dotenv import load_dotenv
load_dotenv()

stripe_bp = Blueprint("stripe_payments", __name__, url_prefix="/api/payments")

# env
STRIPE_SECRET = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
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

# server-side pack truth (subscription)
PACKS = {
    "pro": {"credits": 10, "amount_dollars": 5, "interval": "month"},
}

CUSTOM_USD_PER_CREDIT = 1  # $1 per credit for one-time purchases


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
      - packId == "pro" -> $5/month subscription for 10 credits/month
      - packId == "custom" -> $1 per credit one-time payment
    Returns: { url: "<stripe_checkout_url>" }
    """
    if not STRIPE_SECRET:
        return jsonify({"error": "stripe_not_configured", "message": "Set STRIPE_SECRET_KEY on server"}), 501

    body = request.get_json(silent=True) or {}
    pack_id = body.get("packId", "pro")
    user_id = _resolve_user_id(request) or ""

    current_app.logger.info("checkout request: resolved user_id=%s body=%s", user_id, body)

    origin = (request.headers.get("Origin") or FRONTEND_URL or "").rstrip("/")
    if not origin:
        origin = "http://localhost:5173"

    try:
        # Subscription mode for "pro" pack
        if pack_id == "pro":
            pack = PACKS[pack_id]
            credits = pack["credits"]
            amount_cents = int(round(pack["amount_dollars"] * 100))
            interval = pack.get("interval", "month")
            product_name = f"Pro Subscription — {credits} credits/{interval}"

            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                mode="subscription",
                line_items=[
                    {
                        "price_data": {
                            "currency": "usd",
                            "product_data": {"name": product_name},
                            "unit_amount": amount_cents,
                            "recurring": {"interval": interval},
                        },
                        "quantity": 1,
                    }
                ],
                subscription_data={
                    "metadata": {"user_id": user_id, "pack_id": pack_id, "credits": str(credits)},
                },
                metadata={"user_id": user_id, "pack_id": pack_id, "credits": str(credits)},
                success_url=f"{origin}/pay/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{origin}/pay/cancel",
            )
        # One-time payment for custom credits
        else:
            try:
                credits = int(body.get("credits") or 0)
            except Exception:
                return jsonify({"error": "invalid_credits"}), 400
            if credits < 1:
                return jsonify({"error": "invalid_credits", "message": "Minimum 1 credit"}), 400

            amount_cents = credits * CUSTOM_USD_PER_CREDIT * 100
            product_name = f"Credit Pack — {credits} credits"

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
                metadata={"user_id": user_id, "pack_id": "custom", "credits": str(credits)},
                success_url=f"{origin}/pay/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{origin}/pay/cancel",
            )

        current_app.logger.info("created stripe session id=%s url=%s mode=%s", session.get("id"), session.get("url"), session.get("mode"))
        return jsonify({"url": session.get("url")}), 200
    except stripe.error.StripeError as se:
        current_app.logger.exception("Stripe error during checkout")
        return jsonify({"error": "stripe_error", "message": str(se)}), 502
    except Exception:
        current_app.logger.exception("checkout error")
        return jsonify({"error": "internal_server_error"}), 500


def _grant_credits(uid, credits, stripe_id, amount_cents, status="COMPLETED"):
    """Helper to grant credits and record purchase. Returns True on success."""
    if not SUPABASE or not uid:
        current_app.logger.warning("Cannot grant credits: SUPABASE=%s uid=%s", bool(SUPABASE), uid)
        return False

    try:
        # ensure profile exists
        SUPABASE.table("profiles").upsert({"user_id": uid}).execute()

        # increment credits via RPC or fallback
        try:
            SUPABASE.rpc("increment_profile_credits", {"p_user_id": uid, "p_delta": credits}).execute()
            current_app.logger.info("Incremented %s credits for user %s via RPC", credits, uid)
        except Exception:
            cur = SUPABASE.table("profiles").select("credits").eq("user_id", uid).single().execute()
            current_credits = 0
            if hasattr(cur, "data"):
                current_credits = int((cur.data or {}).get("credits") or 0)
            else:
                current_credits = int((cur.get("data") or {}).get("credits") or 0)
            SUPABASE.table("profiles").update({"credits": current_credits + credits}).eq("user_id", uid).execute()
            current_app.logger.info("Updated user %s credits from %s to %s (fallback)", uid, current_credits, current_credits + credits)

        # insert purchase record
        SUPABASE.table("purchases").insert({
            "user_id": uid,
            "amount_cents": amount_cents,
            "credits_granted": credits,
            "status": status,
            "stripe_session_id": stripe_id,
        }).execute()
        current_app.logger.info("Inserted purchase record for %s user %s credits %s", stripe_id, uid, credits)
        return True
    except Exception:
        current_app.logger.exception("Failed to grant credits")
        return False


def _update_subscription_status(uid, subscription_id, status, period_end=None):
    """Update user's subscription info in profiles table."""
    if not SUPABASE or not uid:
        current_app.logger.warning("Cannot update subscription: SUPABASE=%s uid=%s", bool(SUPABASE), uid)
        return
    try:
        update_data = {
            "subscription_id": subscription_id,
            "subscription_status": status,
        }
        if period_end:
            update_data["subscription_period_end"] = period_end

        SUPABASE.table("profiles").update(update_data).eq("user_id", uid).execute()
        current_app.logger.info("Updated subscription status for user %s: %s (%s)", uid, status, subscription_id)
    except Exception:
        current_app.logger.exception("Failed to update subscription status")


@stripe_bp.post("/webhook")
def webhook():
    """
    Handle Stripe webhooks for subscriptions.
    Events handled:
      - checkout.session.completed: Initial subscription, grant first month credits
      - invoice.paid: Recurring payment, grant monthly credits
      - customer.subscription.deleted: Subscription cancelled
    """
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")
    event = None

    try:
        current_app.logger.debug(
            "Stripe webhook raw payload (trim): %s",
            (payload.decode("utf-8", "replace")[:2000] if payload else ""),
        )
    except Exception:
        current_app.logger.debug("Stripe webhook raw payload (binary) present")

    try:
        if STRIPE_WEBHOOK_SECRET and sig_header:
            event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
        else:
            event = json.loads(payload)
    except Exception:
        current_app.logger.exception("Webhook signature verification failed")
        return jsonify({"error": "invalid_webhook"}), 400

    event_type = event.get("type")
    current_app.logger.info("Webhook received: %s", event_type)

    # Handle checkout completion (both subscription and one-time payment)
    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        stripe_session_id = session.get("id")
        subscription_id = session.get("subscription")
        mode = session.get("mode")  # "subscription" or "payment"

        current_app.logger.info(
            "checkout.session.completed: id=%s, mode=%s, subscription=%s, metadata=%s",
            stripe_session_id, mode, subscription_id, session.get("metadata"),
        )

        metadata = session.get("metadata", {}) or {}
        uid = metadata.get("user_id")

        # For subscriptions, credits are granted via invoice.paid event
        if subscription_id and uid:
            # Retrieve subscription to get period_end
            period_end = None
            try:
                sub = stripe.Subscription.retrieve(subscription_id)
                period_end = getattr(sub, "current_period_end", None) or getattr(sub, "cancel_at", None)
            except Exception as e:
                current_app.logger.warning("Could not retrieve subscription %s for period_end: %s", subscription_id, e)
            _update_subscription_status(uid, subscription_id, "active", period_end)

        # For one-time payments, grant credits immediately
        elif mode == "payment" and uid:
            try:
                credits = int(metadata.get("credits", "0") or 0)
            except Exception:
                credits = 0
            amount_total = int(session.get("amount_total") or 0)

            if credits > 0:
                # Check idempotency
                already_processed = False
                if SUPABASE:
                    try:
                        res = SUPABASE.table("purchases").select("id").eq("stripe_session_id", stripe_session_id).limit(1).execute()
                        already = getattr(res, "data", None) or (res.get("data") if isinstance(res, dict) else None)
                        if already:
                            already_processed = True
                            current_app.logger.info("Session %s already processed, skipping", stripe_session_id)
                    except Exception:
                        current_app.logger.exception("Failed idempotency check")

                if not already_processed:
                    _grant_credits(uid, credits, stripe_session_id, amount_total, "COMPLETED")

    # Handle recurring invoice payments (including first payment)
    elif event_type == "invoice.paid":
        invoice = event["data"]["object"]
        invoice_id = invoice.get("id")
        subscription_id = invoice.get("subscription")
        amount_paid = int(invoice.get("amount_paid") or 0)

        current_app.logger.info(
            "invoice.paid: id=%s, subscription=%s, amount=%s",
            invoice_id, subscription_id, amount_paid,
        )

        # Check idempotency
        if SUPABASE:
            try:
                res = SUPABASE.table("purchases").select("id").eq("stripe_session_id", invoice_id).limit(1).execute()
                already = getattr(res, "data", None) or (res.get("data") if isinstance(res, dict) else None)
                if already:
                    current_app.logger.info("Invoice %s already processed, skipping", invoice_id)
                    return jsonify({"received": True}), 200
            except Exception:
                current_app.logger.exception("Failed idempotency check")

        # Get subscription metadata for user_id and credits
        uid = None
        credits = PACKS.get("pro", {}).get("credits", 10)
        period_end = None

        if subscription_id:
            try:
                sub = stripe.Subscription.retrieve(subscription_id)
                sub_metadata = getattr(sub, "metadata", {}) or {}
                uid = sub_metadata.get("user_id") if isinstance(sub_metadata, dict) else getattr(sub_metadata, "user_id", None)
                period_end = getattr(sub, "current_period_end", None) or getattr(sub, "cancel_at", None)
                credits_str = sub_metadata.get("credits") if isinstance(sub_metadata, dict) else getattr(sub_metadata, "credits", None)
                if credits_str:
                    credits = int(credits_str)
            except Exception:
                current_app.logger.exception("Failed to retrieve subscription %s", subscription_id)

        if uid and credits > 0:
            _grant_credits(uid, credits, invoice_id, amount_paid, "COMPLETED")
            # Also ensure subscription status is saved (fallback if checkout.session.completed missed it)
            if subscription_id:
                _update_subscription_status(uid, subscription_id, "active", period_end)
        else:
            current_app.logger.warning("Cannot grant credits: uid=%s credits=%s", uid, credits)

    # Handle subscription cancellation
    elif event_type == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        subscription_id = subscription.get("id")
        metadata = subscription.get("metadata", {}) or {}
        uid = metadata.get("user_id")

        current_app.logger.info(
            "customer.subscription.deleted: id=%s, user=%s",
            subscription_id, uid,
        )

        if uid:
            _update_subscription_status(uid, subscription_id, "cancelled")

    return jsonify({"received": True}), 200


@stripe_bp.get("/subscription")
def get_subscription():
    """Get current user's subscription status. Also fetches period_end from Stripe if missing."""
    if not STRIPE_SECRET:
        return jsonify({"error": "stripe_not_configured"}), 501

    user_id = _resolve_user_id(request)
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    try:
        if SUPABASE:
            res = SUPABASE.table("profiles").select("subscription_id, subscription_status, subscription_period_end").eq("user_id", user_id).single().execute()
            data = getattr(res, "data", None) or (res.get("data") if isinstance(res, dict) else None)

            if data:
                subscription_id = data.get("subscription_id")
                status = data.get("subscription_status")
                period_end = data.get("subscription_period_end")

                # If we have a subscription but no period_end, fetch it from Stripe
                if subscription_id and status in ("active", "cancelling") and not period_end:
                    try:
                        sub = stripe.Subscription.retrieve(subscription_id)
                        # Try current_period_end first, then cancel_at for cancelled subscriptions
                        period_end = getattr(sub, "current_period_end", None) or getattr(sub, "cancel_at", None)

                        if period_end:
                            _update_subscription_status(user_id, subscription_id, status, period_end)
                            current_app.logger.info("Refreshed period_end for user %s: %s", user_id, period_end)
                    except Exception as e:
                        current_app.logger.exception("Failed to fetch subscription %s from Stripe: %s", subscription_id, e)

                return jsonify({
                    "subscription_id": subscription_id,
                    "status": status,
                    "period_end": period_end,
                }), 200
        return jsonify({"subscription_id": None, "status": None, "period_end": None}), 200
    except Exception:
        current_app.logger.exception("Failed to get subscription status")
        return jsonify({"error": "internal_error"}), 500


@stripe_bp.post("/subscription/cancel")
def cancel_subscription():
    """Cancel user's subscription."""
    if not STRIPE_SECRET:
        return jsonify({"error": "stripe_not_configured"}), 501

    user_id = _resolve_user_id(request)
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    try:
        # Get subscription ID from profile
        if not SUPABASE:
            return jsonify({"error": "database_not_configured"}), 501

        res = SUPABASE.table("profiles").select("subscription_id").eq("user_id", user_id).single().execute()
        data = getattr(res, "data", None) or (res.get("data") if isinstance(res, dict) else None)
        subscription_id = data.get("subscription_id") if data else None

        if not subscription_id:
            return jsonify({"error": "no_active_subscription"}), 400

        # Cancel at period end (user keeps access until billing period ends)
        sub = stripe.Subscription.modify(subscription_id, cancel_at_period_end=True)

        # Get period_end - try current_period_end first, then cancel_at for cancelled subscriptions
        period_end = getattr(sub, "current_period_end", None) or getattr(sub, "cancel_at", None)
        current_app.logger.info("Cancel subscription period_end=%s", period_end)
        _update_subscription_status(user_id, subscription_id, "cancelling", period_end)

        current_app.logger.info("Subscription %s set to cancel at period end for user %s", subscription_id, user_id)
        return jsonify({"ok": True, "message": "Subscription will cancel at end of billing period", "period_end": period_end}), 200
    except stripe.error.StripeError as se:
        current_app.logger.exception("Stripe error cancelling subscription")
        return jsonify({"error": "stripe_error", "message": str(se)}), 502
    except Exception:
        current_app.logger.exception("Failed to cancel subscription")
        return jsonify({"error": "internal_error"}), 500


@stripe_bp.post("/subscription/sync")
def sync_subscription():
    """Sync subscription status from Stripe (call after successful checkout)."""
    if not STRIPE_SECRET:
        return jsonify({"error": "stripe_not_configured"}), 501

    user_id = _resolve_user_id(request)
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    body = request.get_json(silent=True) or {}
    session_id = body.get("session_id")

    if not session_id:
        return jsonify({"error": "missing_session_id"}), 400

    try:
        # Retrieve the checkout session from Stripe
        session = stripe.checkout.Session.retrieve(session_id)
        subscription_id = session.get("subscription")

        if not subscription_id:
            return jsonify({"error": "no_subscription_in_session"}), 400

        # Get subscription details from Stripe
        sub = stripe.Subscription.retrieve(subscription_id)
        period_end = sub.get("current_period_end")  # Unix timestamp

        # Update the user's profile with subscription info
        _update_subscription_status(user_id, subscription_id, "active", period_end)

        current_app.logger.info("Synced subscription %s for user %s from session %s", subscription_id, user_id, session_id)
        return jsonify({"ok": True, "subscription_id": subscription_id, "status": "active", "period_end": period_end}), 200
    except stripe.error.StripeError as se:
        current_app.logger.exception("Stripe error syncing subscription")
        return jsonify({"error": "stripe_error", "message": str(se)}), 502
    except Exception:
        current_app.logger.exception("Failed to sync subscription")
        return jsonify({"error": "internal_error"}), 500


@stripe_bp.post("/subscription/reactivate")
def reactivate_subscription():
    """Reactivate a subscription that was set to cancel at period end."""
    if not STRIPE_SECRET:
        return jsonify({"error": "stripe_not_configured"}), 501

    user_id = _resolve_user_id(request)
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    try:
        if not SUPABASE:
            return jsonify({"error": "database_not_configured"}), 501

        res = SUPABASE.table("profiles").select("subscription_id, subscription_status").eq("user_id", user_id).single().execute()
        data = getattr(res, "data", None) or (res.get("data") if isinstance(res, dict) else None)
        subscription_id = data.get("subscription_id") if data else None
        status = data.get("subscription_status") if data else None

        if not subscription_id:
            return jsonify({"error": "no_subscription"}), 400

        if status != "cancelling":
            return jsonify({"error": "subscription_not_cancelling"}), 400

        # Reactivate by setting cancel_at_period_end to False
        stripe.Subscription.modify(subscription_id, cancel_at_period_end=False)
        _update_subscription_status(user_id, subscription_id, "active")

        current_app.logger.info("Subscription %s reactivated for user %s", subscription_id, user_id)
        return jsonify({"ok": True, "message": "Subscription reactivated"}), 200
    except stripe.error.StripeError as se:
        current_app.logger.exception("Stripe error reactivating subscription")
        return jsonify({"error": "stripe_error", "message": str(se)}), 502
    except Exception:
        current_app.logger.exception("Failed to reactivate subscription")
        return jsonify({"error": "internal_error"}), 500
