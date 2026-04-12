"""Bundle T — Stripe Payment Foundation.

Env-driven configuration so no secrets live in code.

Required env vars (production):
    STRIPE_SECRET_KEY          — sk_live_… or sk_test_…
    STRIPE_WEBHOOK_SECRET      — whsec_…
    STRIPE_PRICE_COMET         — price_… for Comet tier
    STRIPE_PRICE_OPERATOR      — price_… for Operator tier
    STRIPE_PRICE_PROFESSIONAL  — price_… for Professional tier
    STRIPE_PRICE_ELITE         — price_… for Elite tier
"""

import logging
import os
from datetime import datetime, UTC

logger = logging.getLogger(__name__)

_stripe = None  # lazy import


def _get_stripe():
    global _stripe
    if _stripe is None:
        try:
            import stripe

            stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
            _stripe = stripe
        except ImportError:
            logger.warning("stripe package not installed")
    return _stripe


# ------------------------------------------------------------------
# Price map (tier name → Stripe price ID)
# ------------------------------------------------------------------


def get_tier_price_map():
    """Return the current Stripe price mapping from environment."""
    return {
        "comet": os.environ.get("STRIPE_PRICE_COMET", "").strip(),
        "operator": os.environ.get("STRIPE_PRICE_OPERATOR", "").strip(),
        "professional": os.environ.get("STRIPE_PRICE_PROFESSIONAL", "").strip(),
        "elite": os.environ.get("STRIPE_PRICE_ELITE", "").strip(),
    }


def get_price_tier_map():
    """Return inverse Stripe price mapping (price ID -> tier)."""
    return {
        price_id: tier_name
        for tier_name, price_id in get_tier_price_map().items()
        if price_id
    }


def get_stripe_config():
    """Return non-secret config (publishable key, price IDs)."""
    prices = get_tier_price_map()
    missing_prices = [tier for tier, value in prices.items() if not value]
    has_secret_key = bool(os.environ.get("STRIPE_SECRET_KEY", "").strip())
    has_webhook_secret = bool(os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip())
    checkout_ready = has_secret_key and any(prices.values())
    webhook_ready = has_secret_key and has_webhook_secret

    missing = []
    if not has_secret_key:
        missing.append("STRIPE_SECRET_KEY")
    if not has_webhook_secret:
        missing.append("STRIPE_WEBHOOK_SECRET")
    missing.extend(f"STRIPE_PRICE_{tier.upper()}" for tier in missing_prices)

    return {
        "has_secret_key": has_secret_key,
        "has_webhook_secret": has_webhook_secret,
        "prices": {k: v for k, v in prices.items() if v},
        "configured_tiers": [tier for tier, value in prices.items() if value],
        "missing_prices": missing_prices,
        "checkout_ready": checkout_ready,
        "webhook_ready": webhook_ready,
        "mode": "live-checkout" if checkout_ready else "beta-fallback",
        "missing": missing,
        "reason": (
            None
            if checkout_ready
            else (
                "Stripe secret key is missing."
                if not has_secret_key
                else "Stripe prices are missing for all paid tiers."
            )
        ),
    }


# ------------------------------------------------------------------
# Checkout session
# ------------------------------------------------------------------


def create_checkout_session(user, tier_name, success_url, cancel_url):
    """Create a Stripe Checkout session. Returns a structured result dict."""
    stripe = _get_stripe()
    if not stripe or not stripe.api_key:
        logger.warning("Stripe not configured — skipping checkout")
        return {"ok": False, "reason": "stripe not configured"}

    price_id = get_tier_price_map().get(tier_name)
    if not price_id:
        logger.warning("No Stripe price for tier %s", tier_name)
        return {"ok": False, "reason": f"missing price for {tier_name}"}

    if tier_name in ("free", "trial"):
        return {"ok": False, "reason": "invalid checkout tier"}

    try:
        # Ensure customer exists
        customer_id = user.stripe_customer_id
        if not customer_id:
            customer = stripe.Customer.create(
                email=user.email or "",
                metadata={"offerion_user_id": user.id},
            )
            customer_id = customer.id
            # Persist customer ID (caller commits)
            user.stripe_customer_id = customer_id

        checkout = stripe.checkout.Session.create(
            customer=customer_id,
            client_reference_id=user.id,
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"offerion_user_id": user.id, "tier": tier_name},
            subscription_data={
                "metadata": {"offerion_user_id": user.id, "tier": tier_name}
            },
        )
        return {
            "ok": True,
            "url": checkout.url,
            "checkout_session_id": checkout.id,
            "customer_id": customer_id,
            "price_id": price_id,
        }
    except Exception as exc:
        logger.error("create_checkout_session failed: %s", exc)
        return {"ok": False, "reason": str(exc)}


def retrieve_checkout_session(session_id):
    """Fetch a checkout session directly from Stripe."""
    stripe = _get_stripe()
    if not stripe or not stripe.api_key or not session_id:
        return None
    try:
        return stripe.checkout.Session.retrieve(session_id)
    except Exception as exc:
        logger.error("retrieve_checkout_session failed: %s", exc)
        return None


# ------------------------------------------------------------------
# Webhook handling
# ------------------------------------------------------------------


def handle_webhook_event(payload, sig_header):
    """Verify and parse a Stripe webhook. Returns (event, error_msg)."""
    stripe = _get_stripe()
    if not stripe:
        return None, "stripe unavailable"

    secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    if not secret:
        return None, "webhook secret not configured"

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, secret)
        return event, None
    except stripe.error.SignatureVerificationError:
        return None, "invalid signature"
    except Exception as exc:
        return None, str(exc)


def _coerce_period_end(timestamp_value):
    if not timestamp_value:
        return None
    try:
        return datetime.fromtimestamp(int(timestamp_value), UTC).replace(tzinfo=None)
    except Exception:
        return None


def _resolve_tier_from_subscription(sub):
    metadata = sub.get("metadata", {}) or {}
    if metadata.get("tier"):
        return metadata.get("tier")

    price_map = get_price_tier_map()
    items = (sub.get("items") or {}).get("data") or []
    for item in items:
        price_id = ((item.get("price") or {}).get("id") or "").strip()
        if price_id and price_id in price_map:
            return price_map[price_id]
    return None


def _resolve_price_id_from_subscription(sub):
    items = (sub.get("items") or {}).get("data") or []
    for item in items:
        price_id = ((item.get("price") or {}).get("id") or "").strip()
        if price_id:
            return price_id
    return None


def process_checkout_completed(event_data):
    """Handle checkout.session.completed — returns (user_id, tier) or None."""
    session_obj = event_data.get("object", {})
    meta = session_obj.get("metadata", {})
    user_id = meta.get("offerion_user_id")
    tier = meta.get("tier")
    subscription_id = session_obj.get("subscription")
    if not user_id or not tier:
        return None

    return {
        "event_id": session_obj.get("id"),
        "user_id": user_id,
        "tier": tier,
        "subscription_id": subscription_id,
        "customer_id": session_obj.get("customer"),
        "status": "active",
    }


def process_subscription_updated(event_data):
    """Handle customer.subscription.updated / deleted."""
    sub = event_data.get("object", {})
    status = sub.get("status")  # active, canceled, past_due, etc.
    customer_id = sub.get("customer")
    subscription_id = sub.get("id")
    return {
        "user_id": (sub.get("metadata") or {}).get("offerion_user_id"),
        "customer_id": customer_id,
        "subscription_id": subscription_id,
        "status": status,
        "tier": _resolve_tier_from_subscription(sub),
        "price_id": _resolve_price_id_from_subscription(sub),
        "cancel_at_period_end": bool(sub.get("cancel_at_period_end")),
        "current_period_end": _coerce_period_end(sub.get("current_period_end")),
    }


def process_invoice_payment_failed(event_data):
    """Extract billing issue state from invoice payment failures."""
    invoice = event_data.get("object", {})
    return {
        "customer_id": invoice.get("customer"),
        "subscription_id": invoice.get("subscription"),
        "status": "past_due",
    }
