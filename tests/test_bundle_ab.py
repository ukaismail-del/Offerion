"""Tests for Bundle AB — Payment hardening and subscription safety."""

import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_app(**env_overrides):
    previous = {}
    tracked_keys = (
        "DATABASE_URL",
        "STRIPE_SECRET_KEY",
        "STRIPE_WEBHOOK_SECRET",
        "STRIPE_PRICE_COMET",
        "STRIPE_PRICE_OPERATOR",
        "STRIPE_PRICE_PROFESSIONAL",
        "STRIPE_PRICE_ELITE",
    )
    for key in tracked_keys:
        previous[key] = os.environ.get(key)
    os.environ["DATABASE_URL"] = "sqlite://"
    for key, value in env_overrides.items():
        os.environ[key] = value
    try:
        from app import create_app

        app = create_app(testing=True)
    finally:
        for key, old_value in previous.items():
            if key in env_overrides:
                if old_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = old_value
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    return app


def _make_client(**env_overrides):
    app = _make_app(**env_overrides)
    return app, app.test_client()


def _signup(client, email="ab@example.com", password="password123"):
    return client.post(
        "/signup",
        data={"email": email, "password": password},
        follow_redirects=False,
    )


class TestBillingHelpersAB(unittest.TestCase):
    def test_apply_subscription_state_active_sets_paid_fields(self):
        app = _make_app()
        with app.app_context():
            from app.db import db
            from app.models import UserIdentity
            from app.utils.billing import apply_subscription_state

            user = UserIdentity(email="billing-active@test.com", tier="free")
            db.session.add(user)
            db.session.commit()

            apply_subscription_state(
                user,
                "active",
                tier_name="operator",
                subscription_id="sub_123",
                customer_id="cus_123",
                price_id="price_operator",
            )
            self.assertEqual(user.tier, "operator")
            self.assertEqual(user.subscription_status, "active")
            self.assertEqual(user.stripe_subscription_id, "sub_123")
            self.assertEqual(user.stripe_customer_id, "cus_123")
            self.assertEqual(user.stripe_price_id, "price_operator")
            self.assertIsNotNone(user.paid_started_at)
            self.assertFalse(bool(user.cancel_at_period_end))

    def test_apply_subscription_state_past_due_falls_back_to_free(self):
        app = _make_app()
        with app.app_context():
            from app.db import db
            from app.models import UserIdentity
            from app.utils.billing import apply_subscription_state

            user = UserIdentity(email="billing-due@test.com", tier="operator")
            user.subscription_status = "active"
            db.session.add(user)
            db.session.commit()

            apply_subscription_state(user, "past_due", subscription_id="sub_456")
            self.assertEqual(user.tier, "free")
            self.assertEqual(user.subscription_status, "past_due")
            self.assertIsNotNone(user.billing_issue_at)


class TestCheckoutHardening(unittest.TestCase):
    def test_invalid_checkout_tier_fails_safely(self):
        app, client = _make_client()
        _signup(client, email="invalid-tier@test.com")
        resp = client.post("/checkout/free", follow_redirects=True)
        html = resp.data.decode()
        self.assertEqual(resp.status_code, 200)
        self.assertIn("cannot be purchased", html)

    def test_checkout_cancel_route_sets_clean_message(self):
        app, client = _make_client()
        _signup(client, email="cancel@test.com")
        with client.session_transaction() as sess:
            sess["pending_checkout_tier"] = "operator"
        resp = client.get("/checkout/cancel", follow_redirects=True)
        html = resp.data.decode()
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Checkout was canceled", html)

    def test_checkout_success_with_session_id_activates_user(self):
        app, client = _make_client()
        _signup(client, email="success@test.com")
        with app.app_context():
            from app.models import UserIdentity

            user = UserIdentity.query.filter_by(email="success@test.com").first()
            user_id = user.id

        fake_session = {
            "id": "cs_test_1",
            "metadata": {"offerion_user_id": user_id, "tier": "operator"},
            "subscription": "sub_test_1",
            "customer": "cus_test_1",
        }

        with patch(
            "app.utils.stripe_billing.get_stripe_config",
            return_value={"checkout_ready": True},
        ), patch(
            "app.utils.stripe_billing.retrieve_checkout_session",
            return_value=fake_session,
        ):
            resp = client.get(
                "/checkout/success?session_id=cs_test_1", follow_redirects=True
            )

        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode()
        self.assertIn("subscription is active", html)

        with app.app_context():
            from app.models import UserIdentity

            user = UserIdentity.query.filter_by(email="success@test.com").first()
            self.assertEqual(user.tier, "operator")
            self.assertEqual(user.subscription_status, "active")
            self.assertEqual(user.stripe_subscription_id, "sub_test_1")


class TestWebhookSafety(unittest.TestCase):
    def test_duplicate_webhook_delivery_is_idempotent(self):
        app, client = _make_client()
        _signup(client, email="webhook-dup@test.com")
        with app.app_context():
            from app.db import db
            from app.models import UserIdentity

            user = UserIdentity.query.filter_by(email="webhook-dup@test.com").first()
            user.stripe_customer_id = "cus_dup"
            db.session.commit()

        event = {
            "id": "evt_duplicate_1",
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_dup",
                    "customer": "cus_dup",
                    "status": "active",
                    "cancel_at_period_end": False,
                    "current_period_end": 1893456000,
                    "metadata": {"tier": "operator"},
                    "items": {"data": []},
                }
            },
        }

        with patch(
            "app.utils.stripe_billing.handle_webhook_event", return_value=(event, None)
        ):
            first = client.post(
                "/stripe/webhook", data=b"{}", headers={"Stripe-Signature": "sig"}
            )
            second = client.post(
                "/stripe/webhook", data=b"{}", headers={"Stripe-Signature": "sig"}
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)

        with app.app_context():
            from app.models import ProcessedWebhookEvent, UserIdentity

            records = ProcessedWebhookEvent.query.filter_by(
                event_id="evt_duplicate_1"
            ).all()
            user = UserIdentity.query.filter_by(email="webhook-dup@test.com").first()
            self.assertEqual(len(records), 1)
            self.assertEqual(user.subscription_status, "active")
            self.assertEqual(user.tier, "operator")

    def test_payment_failed_webhook_falls_back_to_free(self):
        app, client = _make_client()
        _signup(client, email="webhook-fail@test.com")
        with app.app_context():
            from app.db import db
            from app.models import UserIdentity

            user = UserIdentity.query.filter_by(email="webhook-fail@test.com").first()
            user.stripe_customer_id = "cus_fail"
            user.tier = "operator"
            user.subscription_status = "active"
            db.session.commit()

        event = {
            "id": "evt_payment_failed_1",
            "type": "invoice.payment_failed",
            "data": {"object": {"customer": "cus_fail", "subscription": "sub_fail"}},
        }

        with patch(
            "app.utils.stripe_billing.handle_webhook_event", return_value=(event, None)
        ):
            resp = client.post(
                "/stripe/webhook", data=b"{}", headers={"Stripe-Signature": "sig"}
            )

        self.assertEqual(resp.status_code, 200)
        with app.app_context():
            from app.models import UserIdentity

            user = UserIdentity.query.filter_by(email="webhook-fail@test.com").first()
            self.assertEqual(user.tier, "free")
            self.assertEqual(user.subscription_status, "past_due")
            self.assertIsNotNone(user.billing_issue_at)

    def test_subscription_deleted_falls_back_cleanly(self):
        app, client = _make_client()
        _signup(client, email="webhook-cancel@test.com")
        with app.app_context():
            from app.db import db
            from app.models import UserIdentity

            user = UserIdentity.query.filter_by(email="webhook-cancel@test.com").first()
            user.stripe_customer_id = "cus_cancel"
            user.tier = "operator"
            user.subscription_status = "active"
            db.session.commit()

        event = {
            "id": "evt_cancel_1",
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": "sub_cancel",
                    "customer": "cus_cancel",
                    "status": "canceled",
                    "cancel_at_period_end": False,
                    "current_period_end": 1893456000,
                    "metadata": {"tier": "operator"},
                    "items": {"data": []},
                }
            },
        }

        with patch(
            "app.utils.stripe_billing.handle_webhook_event", return_value=(event, None)
        ):
            resp = client.post(
                "/stripe/webhook", data=b"{}", headers={"Stripe-Signature": "sig"}
            )

        self.assertEqual(resp.status_code, 200)
        with app.app_context():
            from app.models import UserIdentity

            user = UserIdentity.query.filter_by(email="webhook-cancel@test.com").first()
            self.assertEqual(user.tier, "free")
            self.assertEqual(user.subscription_status, "canceled")
            self.assertIsNotNone(user.subscription_canceled_at)


if __name__ == "__main__":
    unittest.main()
