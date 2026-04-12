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
        "reason": None
        if checkout_ready
        else (
            "Stripe secret key is missing."
            if not has_secret_key
            else "Stripe prices are missing for all paid tiers."
        ),
    }


# ------------------------------------------------------------------
# Checkout session
# ------------------------------------------------------------------


def create_checkout_session(user, tier_name, success_url, cancel_url):
    """Create a Stripe Checkout session. Returns session URL or None."""
    stripe = _get_stripe()
    if not stripe or not stripe.api_key:
        logger.warning("Stripe not configured — skipping checkout")
        return None

    price_id = get_tier_price_map().get(tier_name)
    if not price_id:
        logger.warning("No Stripe price for tier %s", tier_name)
        return None

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
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"offerion_user_id": user.id, "tier": tier_name},
        )
        return checkout.url
    except Exception as exc:
        logger.error("create_checkout_session failed: %s", exc)
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
        "user_id": user_id,
        "tier": tier,
        "subscription_id": subscription_id,
        "customer_id": session_obj.get("customer"),
    }


def process_subscription_updated(event_data):
    """Handle customer.subscription.updated / deleted."""
    sub = event_data.get("object", {})
    status = sub.get("status")  # active, canceled, past_due, etc.
    customer_id = sub.get("customer")
    subscription_id = sub.get("id")
    return {
        "customer_id": customer_id,
        "subscription_id": subscription_id,
        "status": status,
    }
