"""Bundle AC — Live Stripe Activation + Production Payment Verification.

Proves the full chain:
  Render Env → Pricing Page → Checkout → Stripe Event → Webhook
  → User Paid State → Entitlement Confirmed

Test sections:
  TAC-01  Stripe config detection (env var matrix)
  TAC-02  Pricing page mode switching (beta ↔ secure-checkout)
  TAC-03  Checkout route behaviour (fallback / live / guard cases)
  TAC-04  Checkout success / cancel paths
  TAC-05  Webhook verification, routing, idempotency
  TAC-06  Subscription state machine (apply_subscription_state)
  TAC-07  End-to-end paid entitlement after simulated webhook
  TAC-08  /healthz deployment traceability route
  TAC-09  /admin/webhooks visibility route
  TAC-10  ProcessedWebhookEvent DB idempotency
"""

import json
import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_USER_ID = "test-user-ac"
_USER_EMAIL = "ac_test@example.com"


def _make_app(**env_overrides):
    """Create an isolated test app with SQLite, overriding env vars as needed."""
    saved = {}
    keys = [
        "DATABASE_URL",
        "STRIPE_SECRET_KEY",
        "STRIPE_WEBHOOK_SECRET",
        "STRIPE_PRICE_COMET",
        "STRIPE_PRICE_OPERATOR",
        "STRIPE_PRICE_PROFESSIONAL",
        "STRIPE_PRICE_ELITE",
        "OFFERION_PAID_EMAILS",
        "OFFERION_ADMIN_EMAILS",
    ]
    for k in keys:
        saved[k] = os.environ.get(k)

    os.environ["DATABASE_URL"] = "sqlite://"
    for k, v in env_overrides.items():
        os.environ[k] = v

    try:
        from app import create_app

        app = create_app(testing=True)
        app.config["TESTING"] = True
        app.config["SECRET_KEY"] = "test-secret-ac"
    finally:
        for k, prev in saved.items():
            if k in env_overrides:
                if prev is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = prev
            elif prev is None:
                os.environ.pop(k, None)

    return app


def _make_client(**env_overrides):
    app = _make_app(**env_overrides)
    return app, app.test_client()


def _seed_user(
    app,
    user_id=_USER_ID,
    email=_USER_EMAIL,
    tier="free",
    subscription_status=None,
    stripe_customer_id=None,
    is_admin=False,
):
    """Create or reset a test user in the DB."""
    from app.db import db
    from app.models import UserIdentity, ActivityEvent, UserState

    with app.app_context():
        ActivityEvent.query.filter_by(user_id=user_id).delete()
        UserState.query.filter_by(user_id=user_id).delete()
        existing = UserIdentity.query.filter_by(id=user_id).first()
        if existing:
            existing.tier = tier
            existing.email = email
            existing.subscription_status = subscription_status
            existing.stripe_customer_id = stripe_customer_id
            existing.is_admin = is_admin
        else:
            user = UserIdentity(
                id=user_id,
                email=email,
                tier=tier,
                subscription_status=subscription_status,
                stripe_customer_id=stripe_customer_id,
                is_admin=is_admin,
            )
            user.set_password("testpass123")
            db.session.add(user)
        db.session.commit()


def _auth_session(client, user_id=_USER_ID, tier="free", is_admin=False):
    """Inject authenticated session."""
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["user_tier"] = tier
        sess["is_authenticated"] = True
        sess["is_admin"] = is_admin


# ---------------------------------------------------------------------------
# TAC-01 — Stripe Config Detection
# ---------------------------------------------------------------------------


class TestTAC01StripeConfigDetection(unittest.TestCase):
    """get_stripe_config() correctly reflects the Render env var matrix."""

    def _cfg(self, **overrides):
        """Call get_stripe_config() with env overrides applied in-process."""
        import importlib
        import app.utils.stripe_billing as sb

        saved = {}
        keys = [
            "STRIPE_SECRET_KEY",
            "STRIPE_WEBHOOK_SECRET",
            "STRIPE_PRICE_COMET",
            "STRIPE_PRICE_OPERATOR",
            "STRIPE_PRICE_PROFESSIONAL",
            "STRIPE_PRICE_ELITE",
        ]
        for k in keys:
            saved[k] = os.environ.get(k)
            os.environ.pop(k, None)

        for k, v in overrides.items():
            os.environ[k] = v
        try:
            # Reset cached stripe object so api_key is re-read
            sb._stripe = None
            return sb.get_stripe_config()
        finally:
            for k, prev in saved.items():
                if prev is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = prev
            sb._stripe = None

    def test_no_keys_checkout_not_ready(self):
        conf = self._cfg()
        self.assertFalse(conf["checkout_ready"])
        self.assertEqual(conf["mode"], "beta-fallback")
        self.assertIn("STRIPE_SECRET_KEY", conf["missing"])

    def test_secret_key_only_no_prices_not_ready(self):
        conf = self._cfg(STRIPE_SECRET_KEY="sk_test_fake")
        self.assertFalse(conf["checkout_ready"])
        self.assertIn("STRIPE_PRICE_OPERATOR", conf["missing"])

    def test_secret_key_plus_one_price_is_ready(self):
        conf = self._cfg(
            STRIPE_SECRET_KEY="sk_test_fake",
            STRIPE_PRICE_OPERATOR="price_fake_op",
        )
        self.assertTrue(conf["checkout_ready"])
        self.assertEqual(conf["mode"], "live-checkout")

    def test_secret_and_all_prices_fully_ready(self):
        conf = self._cfg(
            STRIPE_SECRET_KEY="sk_test_fake",
            STRIPE_PRICE_COMET="price_comet",
            STRIPE_PRICE_OPERATOR="price_op",
            STRIPE_PRICE_PROFESSIONAL="price_pro",
            STRIPE_PRICE_ELITE="price_elite",
        )
        self.assertTrue(conf["checkout_ready"])
        self.assertEqual(
            conf["configured_tiers"], ["comet", "operator", "professional", "elite"]
        )

    def test_webhook_ready_requires_both_keys(self):
        conf_no_wh = self._cfg(STRIPE_SECRET_KEY="sk_test_fake")
        self.assertFalse(conf_no_wh["webhook_ready"])

        conf_with_wh = self._cfg(
            STRIPE_SECRET_KEY="sk_test_fake",
            STRIPE_WEBHOOK_SECRET="whsec_fake",
        )
        self.assertTrue(conf_with_wh["webhook_ready"])

    def test_missing_list_accurate(self):
        conf = self._cfg(
            STRIPE_SECRET_KEY="sk_test_fake",
            STRIPE_PRICE_OPERATOR="price_op",
        )
        # Webhook secret still missing
        self.assertIn("STRIPE_WEBHOOK_SECRET", conf["missing"])
        # operator is configured so its price should NOT be missing
        self.assertNotIn("STRIPE_PRICE_OPERATOR", conf["missing"])

    def test_price_tier_map_inverse(self):
        from app.utils.stripe_billing import get_price_tier_map

        saved_op = os.environ.get("STRIPE_PRICE_OPERATOR")
        os.environ["STRIPE_PRICE_OPERATOR"] = "price_test_op"
        try:
            m = get_price_tier_map()
            self.assertEqual(m.get("price_test_op"), "operator")
        finally:
            if saved_op is None:
                os.environ.pop("STRIPE_PRICE_OPERATOR", None)
            else:
                os.environ["STRIPE_PRICE_OPERATOR"] = saved_op


# ---------------------------------------------------------------------------
# TAC-02 — Pricing Page Mode Switching
# ---------------------------------------------------------------------------


class TestTAC02PricingModeSwitching(unittest.TestCase):
    """Pricing page switches between beta-fallback and secure-checkout modes."""

    def test_beta_mode_text_when_no_stripe(self):
        app, client = _make_client()
        _seed_user(app)
        _auth_session(client)
        resp = client.get("/pricing")
        html = resp.data.decode()
        self.assertEqual(resp.status_code, 200)
        self.assertIn("beta environment", html)
        self.assertNotIn("Secure checkout is enabled", html)

    def test_secure_checkout_text_when_stripe_configured(self):
        app, client = _make_client()
        _seed_user(app)
        _auth_session(client)
        stripe_env = {
            "STRIPE_SECRET_KEY": "sk_test_fake",
            "STRIPE_PRICE_OPERATOR": "price_fake_op",
        }
        with patch.dict(os.environ, stripe_env):
            resp = client.get("/pricing")
        html = resp.data.decode()
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Secure checkout is enabled", html)
        self.assertNotIn("beta environment", html)

    def test_checkout_forms_present_when_stripe_enabled(self):
        app, client = _make_client()
        _seed_user(app)
        _auth_session(client)
        stripe_env = {
            "STRIPE_SECRET_KEY": "sk_test_fake",
            "STRIPE_PRICE_OPERATOR": "price_fake_op",
        }
        with patch.dict(os.environ, stripe_env):
            resp = client.get("/pricing")
        html = resp.data.decode()
        self.assertIn('action="/checkout/', html)

    def test_no_checkout_forms_when_stripe_disabled(self):
        app, client = _make_client()
        _seed_user(app)
        _auth_session(client)
        resp = client.get("/pricing")
        html = resp.data.decode()
        self.assertNotIn('action="/checkout/', html)

    def test_pricing_renders_200_anonymous(self):
        app, client = _make_client()
        resp = client.get("/pricing")
        self.assertEqual(resp.status_code, 200)

    def test_pricing_renders_200_stripe_configured(self):
        app, client = _make_client()
        stripe_env = {
            "STRIPE_SECRET_KEY": "sk_test_fake",
            "STRIPE_PRICE_OPERATOR": "price_fake_op",
        }
        with patch.dict(os.environ, stripe_env):
            resp = client.get("/pricing")
        self.assertEqual(resp.status_code, 200)


# ---------------------------------------------------------------------------
# TAC-03 — Checkout Route Behaviour
# ---------------------------------------------------------------------------


class TestTAC03CheckoutRouteBehaviour(unittest.TestCase):
    """Checkout route: fallback, live, guard cases."""

    def test_checkout_unauthenticated_redirects_to_login(self):
        app, client = _make_client()
        resp = client.post("/checkout/operator")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.headers["Location"].lower())

    def test_checkout_invalid_tier_redirects_to_pricing(self):
        app, client = _make_client()
        _seed_user(app)
        _auth_session(client)
        resp = client.post("/checkout/notarealthing")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("pricing", resp.headers["Location"].lower())

    def test_checkout_free_tier_redirects_to_pricing(self):
        app, client = _make_client()
        _seed_user(app)
        _auth_session(client)
        resp = client.post("/checkout/free")
        self.assertEqual(resp.status_code, 302)

    def test_checkout_trial_tier_redirects_to_pricing(self):
        app, client = _make_client()
        _seed_user(app)
        _auth_session(client)
        resp = client.post("/checkout/trial")
        self.assertEqual(resp.status_code, 302)

    def test_checkout_no_stripe_falls_back_to_upgrade(self):
        """Without Stripe env vars, /checkout/<tier> falls back to /upgrade/<tier>."""
        app, client = _make_client()
        _seed_user(app)
        _auth_session(client)
        resp = client.post("/checkout/operator")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("upgrade", resp.headers["Location"].lower())

    def test_checkout_with_stripe_calls_create_session(self):
        """With Stripe configured, checkout creates a session and redirects to Stripe."""
        app, client = _make_client()
        _seed_user(app)
        _auth_session(client)

        mock_result = {
            "ok": True,
            "url": "https://checkout.stripe.com/pay/cs_test_fake",
            "checkout_session_id": "cs_test_fake",
            "customer_id": "cus_test_fake",
            "price_id": "price_fake_op",
        }
        stripe_env = {
            "STRIPE_SECRET_KEY": "sk_test_fake",
            "STRIPE_PRICE_OPERATOR": "price_fake_op",
        }
        with patch.dict(os.environ, stripe_env):
            with patch(
                "app.utils.stripe_billing.create_checkout_session",
                return_value=mock_result,
            ) as mock_create:
                resp = client.post("/checkout/operator")
                mock_create.assert_called_once()

        self.assertEqual(resp.status_code, 302)
        self.assertIn("stripe.com", resp.headers["Location"])

    def test_checkout_already_subscribed_same_tier_redirects_with_notice(self):
        app, client = _make_client()
        _seed_user(app, tier="operator", subscription_status="active")
        _auth_session(client, tier="operator")
        stripe_env = {
            "STRIPE_SECRET_KEY": "sk_test_fake",
            "STRIPE_PRICE_OPERATOR": "price_fake_op",
        }
        with patch.dict(os.environ, stripe_env):
            resp = client.post("/checkout/operator")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("pricing", resp.headers["Location"].lower())
        # Gate message should indicate already active
        with client.session_transaction() as sess:
            msg = sess.get("gate_message", "")
        self.assertIn("already", msg.lower())

    def test_checkout_stripe_api_error_falls_back_to_pricing(self):
        """If create_checkout_session returns ok=False, redirect to pricing."""
        app, client = _make_client()
        _seed_user(app)
        _auth_session(client)

        stripe_env = {
            "STRIPE_SECRET_KEY": "sk_test_fake",
            "STRIPE_PRICE_OPERATOR": "price_fake_op",
        }
        with patch.dict(os.environ, stripe_env):
            with patch(
                "app.utils.stripe_billing.create_checkout_session",
                return_value={"ok": False, "reason": "network error"},
            ):
                resp = client.post("/checkout/operator")

        self.assertEqual(resp.status_code, 302)
        self.assertIn("pricing", resp.headers["Location"].lower())


# ---------------------------------------------------------------------------
# TAC-04 — Checkout Success / Cancel
# ---------------------------------------------------------------------------


class TestTAC04CheckoutSuccessCancel(unittest.TestCase):
    """Success and cancel redirect paths with correct messages."""

    def test_success_no_session_id_redirects_to_pricing(self):
        app, client = _make_client()
        _seed_user(app)
        _auth_session(client)
        resp = client.get("/checkout/success")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("pricing", resp.headers["Location"].lower())

    def test_success_no_session_id_sets_pending_message(self):
        app, client = _make_client()
        _seed_user(app)
        _auth_session(client)
        client.get("/checkout/success")
        with client.session_transaction() as sess:
            msg = sess.get("gate_message", "")
        self.assertIn("Payment received", msg)

    def test_success_with_session_id_and_stripe_applies_completion(self):
        """With a real session_id and Stripe ready, completion is applied."""
        app, client = _make_client()
        _seed_user(app)
        _auth_session(client)

        fake_session_obj = {
            "id": "cs_test_fake",
            "object": "checkout.session",
            "metadata": {"offerion_user_id": _USER_ID, "tier": "operator"},
            "subscription": "sub_test_fake",
            "customer": "cus_test_fake",
            "payment_status": "paid",
        }
        stripe_env = {
            "STRIPE_SECRET_KEY": "sk_test_fake",
            "STRIPE_PRICE_OPERATOR": "price_fake_op",
        }
        with patch.dict(os.environ, stripe_env):
            with patch(
                "app.utils.stripe_billing.retrieve_checkout_session",
                return_value=fake_session_obj,
            ):
                resp = client.get("/checkout/success?session_id=cs_test_fake")

        self.assertEqual(resp.status_code, 302)
        # User should now be operator/active
        with app.app_context():
            from app.models import UserIdentity

            user = UserIdentity.query.filter_by(id=_USER_ID).first()
            self.assertEqual(user.subscription_status, "active")
            self.assertEqual(user.tier, "operator")

    def test_cancel_redirects_to_pricing(self):
        app, client = _make_client()
        _seed_user(app)
        _auth_session(client)
        resp = client.get("/checkout/cancel")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("pricing", resp.headers["Location"].lower())

    def test_cancel_sets_cancel_message(self):
        app, client = _make_client()
        _seed_user(app)
        _auth_session(client)
        client.get("/checkout/cancel")
        with client.session_transaction() as sess:
            msg = sess.get("gate_message", "")
        self.assertIn("canceled", msg.lower())


# ---------------------------------------------------------------------------
# TAC-05 — Webhook Verification, Routing, Idempotency
# ---------------------------------------------------------------------------


class TestTAC05WebhookVerification(unittest.TestCase):
    """Webhook endpoint: auth, routing, idempotency."""

    def test_webhook_no_secret_configured_returns_400(self):
        app, client = _make_client()
        resp = client.post(
            "/stripe/webhook",
            data=b'{"type":"test"}',
            headers={"Stripe-Signature": "fake_sig"},
        )
        self.assertEqual(resp.status_code, 400)

    def test_webhook_invalid_signature_returns_400(self):
        app, client = _make_client(
            STRIPE_SECRET_KEY="sk_test_fake",
            STRIPE_WEBHOOK_SECRET="whsec_fake",
        )
        resp = client.post(
            "/stripe/webhook",
            data=b'{"type":"test"}',
            headers={"Stripe-Signature": "bad_sig"},
        )
        self.assertEqual(resp.status_code, 400)

    def _post_event(self, client, event_dict):
        """Post a pre-parsed event bypassing signature verification."""
        payload = json.dumps(event_dict).encode()
        mock_event = dict(event_dict)

        with patch(
            "app.utils.stripe_billing.handle_webhook_event",
            return_value=(mock_event, None),
        ):
            return client.post(
                "/stripe/webhook",
                data=payload,
                headers={"Stripe-Signature": "mocked"},
            )

    def test_checkout_session_completed_returns_200(self):
        app, client = _make_client()
        _seed_user(app)
        event = {
            "id": "evt_checkout_ac01",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_ac01",
                    "metadata": {"offerion_user_id": _USER_ID, "tier": "operator"},
                    "subscription": "sub_ac01",
                    "customer": "cus_ac01",
                }
            },
        }
        resp = self._post_event(client, event)
        self.assertEqual(resp.status_code, 200)

    def test_checkout_completed_activates_user(self):
        app, client = _make_client()
        _seed_user(app)
        event = {
            "id": "evt_checkout_ac02",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_ac02",
                    "metadata": {"offerion_user_id": _USER_ID, "tier": "comet"},
                    "subscription": "sub_ac02",
                    "customer": "cus_ac02",
                }
            },
        }
        self._post_event(client, event)
        with app.app_context():
            from app.models import UserIdentity

            user = UserIdentity.query.filter_by(id=_USER_ID).first()
            self.assertEqual(user.subscription_status, "active")
            self.assertEqual(user.tier, "comet")

    def test_subscription_updated_active_paid(self):
        app, client = _make_client()
        _seed_user(app)
        event = {
            "id": "evt_sub_upd_ac01",
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_ac_upd01",
                    "status": "active",
                    "customer": "cus_ac01",
                    "metadata": {"offerion_user_id": _USER_ID, "tier": "professional"},
                    "items": {"data": [{"price": {"id": "price_pro"}}]},
                    "current_period_end": 9999999999,
                    "cancel_at_period_end": False,
                }
            },
        }
        self._post_event(client, event)
        with app.app_context():
            from app.models import UserIdentity

            user = UserIdentity.query.filter_by(id=_USER_ID).first()
            self.assertEqual(user.subscription_status, "active")

    def test_subscription_deleted_cancels_user(self):
        app, client = _make_client()
        _seed_user(app, tier="operator", subscription_status="active")
        event = {
            "id": "evt_sub_del_ac01",
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": "sub_ac_del01",
                    "status": "canceled",
                    "customer": "cus_ac01",
                    "metadata": {"offerion_user_id": _USER_ID},
                    "items": {"data": []},
                    "current_period_end": None,
                    "cancel_at_period_end": False,
                }
            },
        }
        self._post_event(client, event)
        with app.app_context():
            from app.models import UserIdentity

            user = UserIdentity.query.filter_by(id=_USER_ID).first()
            self.assertEqual(user.tier, "free")

    def test_invoice_payment_failed_marks_billing_issue(self):
        app, client = _make_client()
        _seed_user(
            app,
            tier="operator",
            subscription_status="active",
            stripe_customer_id="cus_ac01",
        )
        event = {
            "id": "evt_inv_fail_ac01",
            "type": "invoice.payment_failed",
            "data": {
                "object": {
                    "customer": "cus_ac01",
                    "subscription": "sub_ac01",
                }
            },
        }
        self._post_event(client, event)
        with app.app_context():
            from app.models import UserIdentity

            user = UserIdentity.query.filter_by(id=_USER_ID).first()
            # billing_issue_at should be set
            self.assertIsNotNone(user.billing_issue_at)

    def test_unknown_event_type_returns_200_ignored(self):
        app, client = _make_client()
        event = {
            "id": "evt_unknown_ac01",
            "type": "payment_intent.created",
            "data": {"object": {}},
        }
        resp = self._post_event(client, event)
        self.assertEqual(resp.status_code, 200)

    def test_duplicate_event_idempotent(self):
        """Same event_id processed twice — second call returns 200 without re-applying."""
        app, client = _make_client()
        _seed_user(app)
        event = {
            "id": "evt_dup_ac01",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_dup_ac01",
                    "metadata": {"offerion_user_id": _USER_ID, "tier": "comet"},
                    "subscription": "sub_dup01",
                    "customer": "cus_dup01",
                }
            },
        }
        r1 = self._post_event(client, event)
        r2 = self._post_event(client, event)
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)

        with app.app_context():
            from app.models import ProcessedWebhookEvent

            count = ProcessedWebhookEvent.query.filter_by(
                event_id="evt_dup_ac01"
            ).count()
            self.assertEqual(count, 1)

    def test_webhook_is_csrf_exempt_in_production_mode(self):
        """Stripe webhook must not require CSRF even in production config."""
        from app import create_app

        app = create_app(testing=False)
        app.config["SECRET_KEY"] = "test"
        client = app.test_client()
        resp = client.post(
            "/stripe/webhook",
            data=b"{}",
            headers={"Stripe-Signature": "test"},
        )
        # Should return 400 (bad sig) not 400 CSRF
        self.assertEqual(resp.status_code, 400)
        self.assertNotIn(b"CSRF", resp.data)


# ---------------------------------------------------------------------------
# TAC-06 — Subscription State Machine
# ---------------------------------------------------------------------------


class TestTAC06SubscriptionStateMachine(unittest.TestCase):
    """apply_subscription_state() and get_user_plan_state() transitions."""

    def _fresh_user(self, app):
        with app.app_context():
            from app.models import UserIdentity

            return UserIdentity.query.filter_by(id=_USER_ID).first()

    def test_active_status_sets_paid_tier(self):
        from app.utils.billing import apply_subscription_state

        app, _ = _make_client()
        _seed_user(app)
        with app.app_context():
            from app.db import db
            from app.models import UserIdentity

            user = UserIdentity.query.filter_by(id=_USER_ID).first()
            apply_subscription_state(
                user,
                "active",
                tier_name="operator",
                subscription_id="sub_x",
                customer_id="cus_x",
            )
            db.session.commit()
            self.assertEqual(user.tier, "operator")
            self.assertEqual(user.subscription_status, "active")
            self.assertIsNotNone(user.paid_started_at)
            self.assertIsNone(user.billing_issue_at)

    def test_trialing_status_grants_paid_access(self):
        from app.utils.billing import apply_subscription_state, get_user_plan_state

        app, _ = _make_client()
        _seed_user(app)
        with app.app_context():
            from app.db import db
            from app.models import UserIdentity

            user = UserIdentity.query.filter_by(id=_USER_ID).first()
            apply_subscription_state(user, "trialing", tier_name="comet")
            db.session.commit()
            plan = get_user_plan_state(user)
            self.assertEqual(plan, "paid")

    def test_canceled_status_reverts_to_free(self):
        from app.utils.billing import apply_subscription_state, get_user_plan_state

        app, _ = _make_client()
        _seed_user(app, tier="operator", subscription_status="active")
        with app.app_context():
            from app.db import db
            from app.models import UserIdentity

            user = UserIdentity.query.filter_by(id=_USER_ID).first()
            apply_subscription_state(user, "canceled")
            db.session.commit()
            self.assertEqual(user.tier, "free")
            self.assertIsNotNone(user.subscription_canceled_at)
            plan = get_user_plan_state(user)
            self.assertEqual(plan, "free")

    def test_past_due_sets_billing_issue(self):
        from app.utils.billing import apply_subscription_state

        app, _ = _make_client()
        _seed_user(app, tier="operator", subscription_status="active")
        with app.app_context():
            from app.db import db
            from app.models import UserIdentity

            user = UserIdentity.query.filter_by(id=_USER_ID).first()
            apply_subscription_state(user, "past_due")
            db.session.commit()
            self.assertIsNotNone(user.billing_issue_at)
            self.assertEqual(user.tier, "free")

    def test_get_plan_state_free_user(self):
        from app.utils.billing import get_user_plan_state

        app, _ = _make_client()
        _seed_user(app, tier="free", subscription_status=None)
        with app.app_context():
            from app.models import UserIdentity

            user = UserIdentity.query.filter_by(id=_USER_ID).first()
            self.assertEqual(get_user_plan_state(user), "free")

    def test_get_plan_state_active_subscription(self):
        from app.utils.billing import get_user_plan_state

        app, _ = _make_client()
        _seed_user(app, tier="operator", subscription_status="active")
        with app.app_context():
            from app.models import UserIdentity

            user = UserIdentity.query.filter_by(id=_USER_ID).first()
            self.assertEqual(get_user_plan_state(user), "paid")

    def test_get_plan_state_trial_active(self):
        from app.utils.billing import get_user_plan_state
        from app.utils.tier_config import start_trial

        app, _ = _make_client()
        _seed_user(app, tier="trial")
        with app.app_context():
            from app.db import db
            from app.models import UserIdentity

            user = UserIdentity.query.filter_by(id=_USER_ID).first()
            start_trial(user)
            db.session.commit()
            self.assertEqual(get_user_plan_state(user), "trial")

    def test_get_plan_state_trial_expired(self):
        from app.utils.billing import get_user_plan_state

        app, _ = _make_client()
        _seed_user(app, tier="trial")
        with app.app_context():
            from app.db import db
            from app.models import UserIdentity

            user = UserIdentity.query.filter_by(id=_USER_ID).first()
            user.trial_end = datetime.utcnow() - timedelta(days=1)
            db.session.commit()
            self.assertEqual(get_user_plan_state(user), "free")

    def test_incomplete_expired_reverts_to_free(self):
        from app.utils.billing import apply_subscription_state

        app, _ = _make_client()
        _seed_user(app, tier="operator", subscription_status="active")
        with app.app_context():
            from app.db import db
            from app.models import UserIdentity

            user = UserIdentity.query.filter_by(id=_USER_ID).first()
            apply_subscription_state(user, "incomplete_expired")
            db.session.commit()
            self.assertEqual(user.tier, "free")

    def test_cancel_at_period_end_stored(self):
        from app.utils.billing import apply_subscription_state

        app, _ = _make_client()
        _seed_user(app, tier="operator", subscription_status="active")
        with app.app_context():
            from app.db import db
            from app.models import UserIdentity

            user = UserIdentity.query.filter_by(id=_USER_ID).first()
            apply_subscription_state(
                user,
                "active",
                tier_name="operator",
                cancel_at_period_end=True,
            )
            db.session.commit()
            self.assertTrue(user.cancel_at_period_end)


# ---------------------------------------------------------------------------
# TAC-07 — End-to-End Paid Entitlement After Simulated Webhook
# ---------------------------------------------------------------------------


class TestTAC07EndToEndEntitlement(unittest.TestCase):
    """Full chain: free user → checkout.session.completed → paid entitlements."""

    def test_free_user_becomes_paid_after_checkout_webhook(self):
        app, client = _make_client()
        _seed_user(app, tier="free", subscription_status=None)

        event = {
            "id": "evt_e2e_ac01",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_e2e_ac01",
                    "metadata": {"offerion_user_id": _USER_ID, "tier": "operator"},
                    "subscription": "sub_e2e01",
                    "customer": "cus_e2e01",
                }
            },
        }
        with patch(
            "app.utils.stripe_billing.handle_webhook_event", return_value=(event, None)
        ):
            resp = client.post(
                "/stripe/webhook",
                data=json.dumps(event).encode(),
                headers={"Stripe-Signature": "mocked"},
            )
        self.assertEqual(resp.status_code, 200)

        with app.app_context():
            from app.models import UserIdentity
            from app.utils.billing import get_user_plan_state, can_run_resume_analysis

            user = UserIdentity.query.filter_by(id=_USER_ID).first()
            self.assertEqual(user.subscription_status, "active")
            self.assertEqual(user.tier, "operator")
            self.assertEqual(get_user_plan_state(user), "paid")
            # Paid users have unlimited analysis access
            self.assertTrue(can_run_resume_analysis(user))

    def test_paid_user_pricing_shows_current_plan(self):
        """After activation, pricing page marks the paid tier as 'Current Plan'."""
        app, client = _make_client(
            STRIPE_SECRET_KEY="sk_test_fake",
            STRIPE_PRICE_OPERATOR="price_fake_op",
        )
        _seed_user(app, tier="operator", subscription_status="active")
        _auth_session(client, tier="operator")

        resp = client.get("/pricing")
        html = resp.data.decode()
        self.assertIn("Current Plan", html)

    def test_canceled_user_loses_entitlement(self):
        app, client = _make_client()
        _seed_user(
            app,
            tier="operator",
            subscription_status="active",
            stripe_customer_id="cus_cancel01",
        )

        event = {
            "id": "evt_cancel_e2e01",
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": "sub_cancel01",
                    "status": "canceled",
                    "customer": "cus_cancel01",
                    "metadata": {"offerion_user_id": _USER_ID},
                    "items": {"data": []},
                    "current_period_end": None,
                    "cancel_at_period_end": False,
                }
            },
        }
        with patch(
            "app.utils.stripe_billing.handle_webhook_event", return_value=(event, None)
        ):
            client.post(
                "/stripe/webhook",
                data=json.dumps(event).encode(),
                headers={"Stripe-Signature": "mocked"},
            )

        with app.app_context():
            from app.models import UserIdentity
            from app.utils.billing import get_user_plan_state

            user = UserIdentity.query.filter_by(id=_USER_ID).first()
            self.assertEqual(user.tier, "free")
            self.assertEqual(get_user_plan_state(user), "free")


# ---------------------------------------------------------------------------
# TAC-08 — /healthz Deployment Traceability Route
# ---------------------------------------------------------------------------


class TestTAC08Healthz(unittest.TestCase):
    """/healthz returns JSON status + commit info with no secrets."""

    def test_healthz_returns_200(self):
        app, client = _make_client()
        resp = client.get("/healthz")
        self.assertEqual(resp.status_code, 200)

    def test_healthz_returns_json(self):
        app, client = _make_client()
        resp = client.get("/healthz")
        self.assertEqual(resp.content_type, "application/json")
        data = json.loads(resp.data)
        self.assertIsInstance(data, dict)

    def test_healthz_has_required_fields(self):
        app, client = _make_client()
        resp = client.get("/healthz")
        data = json.loads(resp.data)
        for field in (
            "status",
            "commit",
            "env",
            "stripe_ready",
            "webhook_ready",
            "stripe_mode",
            "timestamp",
        ):
            self.assertIn(field, data, f"Missing field: {field}")

    def test_healthz_status_is_ok(self):
        app, client = _make_client()
        resp = client.get("/healthz")
        data = json.loads(resp.data)
        self.assertEqual(data["status"], "ok")

    def test_healthz_stripe_ready_false_when_no_config(self):
        app, client = _make_client()
        resp = client.get("/healthz")
        data = json.loads(resp.data)
        self.assertFalse(data["stripe_ready"])
        self.assertEqual(data["stripe_mode"], "beta-fallback")

    def test_healthz_stripe_ready_true_when_configured(self):
        app, client = _make_client()
        stripe_env = {
            "STRIPE_SECRET_KEY": "sk_test_fake",
            "STRIPE_PRICE_OPERATOR": "price_fake_op",
        }
        with patch.dict(os.environ, stripe_env):
            resp = client.get("/healthz")
        data = json.loads(resp.data)
        self.assertTrue(data["stripe_ready"])
        self.assertEqual(data["stripe_mode"], "live-checkout")

    def test_healthz_commit_field_is_string(self):
        app, client = _make_client()
        resp = client.get("/healthz")
        data = json.loads(resp.data)
        self.assertIsInstance(data["commit"], str)
        self.assertGreater(len(data["commit"]), 0)

    def test_healthz_render_git_commit_env_used(self):
        """When RENDER_GIT_COMMIT is set, /healthz reflects it."""
        saved = os.environ.get("RENDER_GIT_COMMIT")
        os.environ["RENDER_GIT_COMMIT"] = "abc123fullsha"
        try:
            app, client = _make_client()
            resp = client.get("/healthz")
            data = json.loads(resp.data)
            self.assertEqual(data["commit"], "abc123fullsha"[:12])
        finally:
            if saved is None:
                os.environ.pop("RENDER_GIT_COMMIT", None)
            else:
                os.environ["RENDER_GIT_COMMIT"] = saved

    def test_healthz_no_secret_keys_in_response(self):
        """Response must never contain the word 'secret' or a key-like value."""
        app, client = _make_client()
        with patch.dict(
            os.environ, {"STRIPE_SECRET_KEY": "sk_test_super_secret_do_not_leak"}
        ):
            resp = client.get("/healthz")
        body = resp.data.decode()
        self.assertNotIn("sk_test_super_secret_do_not_leak", body)
        self.assertNotIn("whsec_", body)


# ---------------------------------------------------------------------------
# TAC-09 — /admin/webhooks Visibility Route
# ---------------------------------------------------------------------------


class TestTAC09AdminWebhooks(unittest.TestCase):
    """/admin/webhooks is admin-gated and returns JSON event list."""

    def test_unauthenticated_redirects_to_login(self):
        app, client = _make_client()
        resp = client.get("/admin/webhooks")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.headers["Location"].lower())

    def test_non_admin_returns_403(self):
        app, client = _make_client()
        _seed_user(app, is_admin=False)
        _auth_session(client, is_admin=False)
        resp = client.get("/admin/webhooks")
        self.assertEqual(resp.status_code, 403)

    def test_admin_returns_200_json(self):
        app, client = _make_client()
        _seed_user(app, is_admin=True)
        _auth_session(client, is_admin=True)
        resp = client.get("/admin/webhooks")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertIn("events", data)
        self.assertIn("count", data)
        self.assertIsInstance(data["events"], list)

    def test_admin_webhooks_shows_processed_events(self):
        app, client = _make_client()
        _seed_user(app, is_admin=True)
        _auth_session(client, is_admin=True)

        # Create a webhook event record directly in DB
        with app.app_context():
            from app.db import db
            from app.models import ProcessedWebhookEvent

            rec = ProcessedWebhookEvent(
                event_id="evt_vis_ac01",
                event_type="checkout.session.completed",
                status="processed",
                user_id=_USER_ID,
            )
            db.session.add(rec)
            db.session.commit()

        resp = client.get("/admin/webhooks")
        data = json.loads(resp.data)
        event_ids = [e["event_id"] for e in data["events"]]
        self.assertIn("evt_vis_ac01", event_ids)


# ---------------------------------------------------------------------------
# TAC-10 — ProcessedWebhookEvent DB Idempotency
# ---------------------------------------------------------------------------


class TestTAC10WebhookEventIdempotency(unittest.TestCase):
    """ProcessedWebhookEvent table enforces idempotent processing."""

    def test_record_created_on_first_write(self):
        app, _ = _make_client()
        with app.app_context():
            from app.db import db
            from app.models import ProcessedWebhookEvent

            rec = ProcessedWebhookEvent(
                event_id="evt_idem_ac01",
                event_type="checkout.session.completed",
                status="processed",
            )
            db.session.add(rec)
            db.session.commit()

            found = ProcessedWebhookEvent.query.filter_by(
                event_id="evt_idem_ac01"
            ).first()
            self.assertIsNotNone(found)
            self.assertEqual(found.status, "processed")

    def test_duplicate_event_id_not_double_inserted(self):
        app, client = _make_client()
        _seed_user(app)
        event = {
            "id": "evt_idem_ac02",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_idem02",
                    "metadata": {"offerion_user_id": _USER_ID, "tier": "comet"},
                    "subscription": "sub_idem02",
                    "customer": "cus_idem02",
                }
            },
        }
        # Post twice
        for _ in range(2):
            with patch(
                "app.utils.stripe_billing.handle_webhook_event",
                return_value=(event, None),
            ):
                client.post(
                    "/stripe/webhook",
                    data=json.dumps(event).encode(),
                    headers={"Stripe-Signature": "mocked"},
                )

        with app.app_context():
            from app.models import ProcessedWebhookEvent

            count = ProcessedWebhookEvent.query.filter_by(
                event_id="evt_idem_ac02"
            ).count()
            self.assertEqual(count, 1)

    def test_event_record_stores_user_id(self):
        app, client = _make_client()
        _seed_user(app)
        event = {
            "id": "evt_idem_ac03",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_idem03",
                    "metadata": {"offerion_user_id": _USER_ID, "tier": "operator"},
                    "subscription": "sub_idem03",
                    "customer": "cus_idem03",
                }
            },
        }
        with patch(
            "app.utils.stripe_billing.handle_webhook_event", return_value=(event, None)
        ):
            client.post(
                "/stripe/webhook",
                data=json.dumps(event).encode(),
                headers={"Stripe-Signature": "mocked"},
            )

        with app.app_context():
            from app.models import ProcessedWebhookEvent

            rec = ProcessedWebhookEvent.query.filter_by(
                event_id="evt_idem_ac03"
            ).first()
            self.assertIsNotNone(rec)
            self.assertEqual(rec.user_id, _USER_ID)

    def test_ignored_event_type_stored_with_ignored_status(self):
        app, client = _make_client()
        event = {
            "id": "evt_ignored_ac01",
            "type": "payment_method.attached",
            "data": {"object": {}},
        }
        with patch(
            "app.utils.stripe_billing.handle_webhook_event", return_value=(event, None)
        ):
            resp = client.post(
                "/stripe/webhook",
                data=json.dumps(event).encode(),
                headers={"Stripe-Signature": "mocked"},
            )
        self.assertEqual(resp.status_code, 200)

        with app.app_context():
            from app.models import ProcessedWebhookEvent

            rec = ProcessedWebhookEvent.query.filter_by(
                event_id="evt_ignored_ac01"
            ).first()
            self.assertIsNotNone(rec)
            self.assertEqual(rec.status, "ignored")


if __name__ == "__main__":
    unittest.main(verbosity=2)
