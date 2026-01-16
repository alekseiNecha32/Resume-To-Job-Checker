import os
import json
import stripe
from flask import Blueprint, request, jsonify, current_app
from supabase import create_client
from dotenv import load_dotenv
load_dotenv()

stripe_bp = Blueprint("stripe_payments", __name__, url_prefix="/api/payments")

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
            if SUPABASE:
                resp = None
                # Try different Supabase client versions
                if hasattr(SUPABASE.auth, "get_user"):
                    resp = SUPABASE.auth.get_user(token)
                elif hasattr(SUPABASE.auth, "api") and hasattr(SUPABASE.auth.api, "get_user"):
                    resp = SUPABASE.auth.api.get_user(token)

                if resp:
                    # Handle different response formats
                    user = None
                    # Supabase v2: resp.user is the user object directly
                    if hasattr(resp, "user") and resp.user:
                        user = resp.user
                    # Dict response format
                    elif isinstance(resp, dict):
                        user = resp.get("user") or (resp.get("data") or {}).get("user")

                    if user:
                        uid = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
                        if uid:
                            current_app.logger.debug("Resolved user_id from token: %s", uid)
                            return uid

                current_app.logger.warning("Could not extract user_id from supabase response: %s", type(resp))
        except Exception as e:
            current_app.logger.warning("supabase get_user failed: %s", str(e))

    # fallback for local/dev: X-User-Id header
    fallback_id = req.headers.get("X-User-Id")
    if fallback_id:
        current_app.logger.debug("Using fallback X-User-Id header: %s", fallback_id)
    return fallback_id


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

    if not user_id:
        current_app.logger.error("checkout request: NO USER_ID RESOLVED - auth header: %s", request.headers.get("Authorization", "")[:50] if request.headers.get("Authorization") else "None")
        return jsonify({"error": "unauthorized", "message": "Could not resolve user identity"}), 401

    current_app.logger.info("checkout request: resolved user_id=%s body=%s", user_id, body)

    origin = (request.headers.get("Origin") or FRONTEND_URL or "").rstrip("/")
    if not origin:
        origin = "http://localhost:5173"

    try:
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
        SUPABASE.table("profiles").upsert({"user_id": uid}).execute()

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

        if subscription_id and uid:
            period_end = None
            try:
                sub = stripe.Subscription.retrieve(subscription_id)
                period_end = getattr(sub, "current_period_end", None) or getattr(sub, "cancel_at", None)
            except Exception as e:
                current_app.logger.warning("Could not retrieve subscription %s for period_end: %s", subscription_id, e)
            _update_subscription_status(uid, subscription_id, "active", period_end)

            # Grant first month credits immediately on subscription creation
            try:
                credits = int(metadata.get("credits", "0") or 0)
            except Exception:
                credits = PACKS.get("pro", {}).get("credits", 10)
            amount_total = int(session.get("amount_total") or 0)

            if credits > 0:
                # Use session_id for idempotency to prevent duplicate grants
                already_processed = False
                if SUPABASE:
                    try:
                        res = SUPABASE.table("purchases").select("id").eq("stripe_session_id", stripe_session_id).limit(1).execute()
                        already = getattr(res, "data", None) or (res.get("data") if isinstance(res, dict) else None)
                        if already:
                            already_processed = True
                            current_app.logger.info("Subscription session %s already processed, skipping credit grant", stripe_session_id)
                    except Exception:
                        current_app.logger.exception("Failed idempotency check for subscription")

                if not already_processed:
                    _grant_credits(uid, credits, stripe_session_id, amount_total, "SUBSCRIPTION_INITIAL")

        elif mode == "payment" and uid:
            try:
                credits = int(metadata.get("credits", "0") or 0)
            except Exception:
                credits = 0
            amount_total = int(session.get("amount_total") or 0)

            if credits > 0:
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
                    _grant_credits(uid, credits, stripe_session_id, amount_total, "ONE_TIME_PURCHASE")

    elif event_type == "invoice.paid":
        invoice = event["data"]["object"]
        invoice_id = invoice.get("id")
        subscription_id = invoice.get("subscription")
        amount_paid = int(invoice.get("amount_paid") or 0)
        billing_reason = invoice.get("billing_reason")

        current_app.logger.info(
            "invoice.paid: id=%s, subscription=%s, amount=%s, billing_reason=%s",
            invoice_id, subscription_id, amount_paid, billing_reason,
        )

        # Skip initial subscription invoice - credits are granted in checkout.session.completed
        if billing_reason == "subscription_create":
            current_app.logger.info("Skipping invoice %s - initial subscription handled by checkout.session.completed", invoice_id)
            return jsonify({"received": True}), 200

        if SUPABASE:
            try:
                res = SUPABASE.table("purchases").select("id").eq("stripe_session_id", invoice_id).limit(1).execute()
                already = getattr(res, "data", None) or (res.get("data") if isinstance(res, dict) else None)
                if already:
                    current_app.logger.info("Invoice %s already processed, skipping", invoice_id)
                    return jsonify({"received": True}), 200
            except Exception:
                current_app.logger.exception("Failed idempotency check")

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
            _grant_credits(uid, credits, invoice_id, amount_paid, "SUBSCRIPTION_RENEWAL")
            if subscription_id:
                _update_subscription_status(uid, subscription_id, "active", period_end)
        else:
            current_app.logger.warning("Cannot grant credits: uid=%s credits=%s", uid, credits)

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

                if subscription_id and status in ("active", "cancelling"):
                    try:
                        sub = stripe.Subscription.retrieve(subscription_id)
                        stripe_status = getattr(sub, "status", None)

                        if stripe_status == "canceled" and status != "cancelled":
                            _update_subscription_status(user_id, None, "cancelled")
                            status = "cancelled"
                            subscription_id = None
                            current_app.logger.info("Synced cancelled status for user %s", user_id)
                        elif not period_end:
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
        if not SUPABASE:
            return jsonify({"error": "database_not_configured"}), 501

        res = SUPABASE.table("profiles").select("subscription_id").eq("user_id", user_id).single().execute()
        data = getattr(res, "data", None) or (res.get("data") if isinstance(res, dict) else None)
        subscription_id = data.get("subscription_id") if data else None

        if not subscription_id:
            return jsonify({"error": "no_active_subscription"}), 400

        sub = stripe.Subscription.modify(subscription_id, cancel_at_period_end=True)
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
        session = stripe.checkout.Session.retrieve(session_id)
        subscription_id = session.get("subscription")
        mode = session.get("mode")
        metadata = session.get("metadata", {}) or {}

        # Handle one-time payments
        if mode == "payment":
            try:
                credits = int(metadata.get("credits", "0") or 0)
            except Exception:
                credits = 0
            amount_total = int(session.get("amount_total") or 0)

            if credits > 0:
                # Check if already processed
                already_processed = False
                if SUPABASE:
                    try:
                        res = SUPABASE.table("purchases").select("id").eq("stripe_session_id", session_id).limit(1).execute()
                        already = getattr(res, "data", None) or (res.get("data") if isinstance(res, dict) else None)
                        if already:
                            already_processed = True
                            current_app.logger.info("Session %s already processed via sync", session_id)
                    except Exception:
                        current_app.logger.exception("Failed idempotency check in sync")

                if not already_processed:
                    _grant_credits(user_id, credits, session_id, amount_total, "ONE_TIME_PURCHASE_SYNC")
                    current_app.logger.info("Granted %s credits to user %s via sync (one-time)", credits, user_id)

            return jsonify({"ok": True, "credits_granted": credits if not already_processed else 0}), 200

        # Handle subscriptions
        if not subscription_id:
            return jsonify({"error": "no_subscription_in_session"}), 400

        sub = stripe.Subscription.retrieve(subscription_id)
        period_end = sub.get("current_period_end")

        _update_subscription_status(user_id, subscription_id, "active", period_end)

        # Grant initial credits if not already granted (fallback for webhook)
        try:
            credits = int(metadata.get("credits", "0") or 0)
        except Exception:
            credits = PACKS.get("pro", {}).get("credits", 10)
        amount_total = int(session.get("amount_total") or 0)

        credits_granted = 0
        if credits > 0:
            # Check if already processed by webhook
            already_processed = False
            if SUPABASE:
                try:
                    res = SUPABASE.table("purchases").select("id").eq("stripe_session_id", session_id).limit(1).execute()
                    already = getattr(res, "data", None) or (res.get("data") if isinstance(res, dict) else None)
                    if already:
                        already_processed = True
                        current_app.logger.info("Session %s already processed, skipping credit grant in sync", session_id)
                except Exception:
                    current_app.logger.exception("Failed idempotency check in sync")

            if not already_processed:
                _grant_credits(user_id, credits, session_id, amount_total, "SUBSCRIPTION_INITIAL_SYNC")
                credits_granted = credits
                current_app.logger.info("Granted %s credits to user %s via sync (subscription)", credits, user_id)

        current_app.logger.info("Synced subscription %s for user %s from session %s", subscription_id, user_id, session_id)
        return jsonify({"ok": True, "subscription_id": subscription_id, "status": "active", "period_end": period_end, "credits_granted": credits_granted}), 200
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

        sub = stripe.Subscription.retrieve(subscription_id)
        stripe_status = getattr(sub, "status", None)

        if stripe_status == "canceled":
            _update_subscription_status(user_id, None, "cancelled")
            return jsonify({"error": "subscription_already_cancelled", "message": "This subscription has ended. Please subscribe again."}), 400

        if stripe_status != "active":
            return jsonify({"error": "subscription_not_active", "message": f"Subscription status is {stripe_status}"}), 400

        stripe.Subscription.modify(subscription_id, cancel_at_period_end=False)
        _update_subscription_status(user_id, subscription_id, "active")

        current_app.logger.info("Subscription %s reactivated for user %s", subscription_id, user_id)
        return jsonify({"ok": True, "message": "Subscription reactivated"}), 200
    except stripe.error.InvalidRequestError as se:
        if "canceled" in str(se).lower():
            _update_subscription_status(user_id, None, "cancelled")
            return jsonify({"error": "subscription_already_cancelled", "message": "This subscription has ended. Please subscribe again."}), 400
        current_app.logger.exception("Stripe error reactivating subscription")
        return jsonify({"error": "stripe_error", "message": str(se)}), 502
    except stripe.error.StripeError as se:
        current_app.logger.exception("Stripe error reactivating subscription")
        return jsonify({"error": "stripe_error", "message": str(se)}), 502
    except Exception:
        current_app.logger.exception("Failed to reactivate subscription")
        return jsonify({"error": "internal_error"}), 500
