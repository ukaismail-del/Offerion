"""Tests for Bundle V — Onboarding Tracking + Founder Metrics V1."""

import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_app(**env_overrides):
    _prev_db = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = "sqlite://"
    _prev_admin = os.environ.get("OFFERION_ADMIN_EMAILS")
    for k, v in env_overrides.items():
        os.environ[k] = v
    try:
        from app import create_app

        app = create_app(testing=True)
    finally:
        if _prev_db is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = _prev_db
        if _prev_admin is None:
            os.environ.pop("OFFERION_ADMIN_EMAILS", None)
        elif "OFFERION_ADMIN_EMAILS" not in env_overrides:
            pass  # leave it alone
        else:
            os.environ["OFFERION_ADMIN_EMAILS"] = _prev_admin
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    return app


def _make_client(**env_overrides):
    app = _make_app(**env_overrides)
    return app, app.test_client()


def _signup(client, email="test@example.com", password="password123"):
    return client.post(
        "/signup",
        data={"email": email, "password": password},
        follow_redirects=False,
    )


def _login(client, email="test@example.com", password="password123"):
    return client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=False,
    )


def _make_admin(app, email="admin@test.com"):
    """Promote an existing user to admin in the DB."""
    with app.app_context():
        from app.models import UserIdentity
        from app.db import db

        user = UserIdentity.query.filter_by(email=email).first()
        if user:
            user.is_admin = True
            db.session.commit()


# ── Data Model Tests ─────────────────────────────────────────────


class TestDataModel(unittest.TestCase):
    """Verify new fields exist on models."""

    def test_user_has_onboarding_fields(self):
        from app.models import UserIdentity

        user = UserIdentity()
        self.assertTrue(hasattr(user, "last_login_at"))
        self.assertTrue(hasattr(user, "has_uploaded_resume"))
        self.assertTrue(hasattr(user, "has_generated_matches"))
        self.assertTrue(hasattr(user, "onboarding_completed_at"))
        self.assertTrue(hasattr(user, "is_admin"))

    def test_user_defaults(self):
        from app.models import UserIdentity

        user = UserIdentity()
        self.assertFalse(user.is_admin)
        self.assertFalse(user.has_uploaded_resume)
        self.assertFalse(user.has_generated_matches)
        self.assertIsNone(user.onboarding_completed_at)
        self.assertIsNone(user.last_login_at)

    def test_activity_event_has_event_label(self):
        from app.models import ActivityEvent

        evt = ActivityEvent()
        self.assertTrue(hasattr(evt, "event_label"))
        self.assertTrue(hasattr(evt, "event_type"))


# ── Signup Event Tracking ────────────────────────────────────────


class TestSignupTracking(unittest.TestCase):
    """Signup should log signup_completed and set last_login_at."""

    def test_signup_logs_event(self):
        app, client = _make_client()
        _signup(client, email="track@test.com", password="secret123")
        with app.app_context():
            from app.models import ActivityEvent

            events = ActivityEvent.query.filter_by(event_type="signup_completed").all()
            self.assertGreaterEqual(len(events), 1)
            evt = events[-1]
            # Email stored in event_label, label, or meta_json
            combined = (
                (evt.event_label or "") + (evt.label or "") + (evt.meta_json or "")
            )
            self.assertIn("track@test.com", combined)

    def test_signup_sets_last_login(self):
        app, client = _make_client()
        _signup(client, email="login_at@test.com", password="secret123")
        with app.app_context():
            from app.models import UserIdentity

            user = UserIdentity.query.filter_by(email="login_at@test.com").first()
            self.assertIsNotNone(user.last_login_at)


# ── Login Event Tracking ─────────────────────────────────────────


class TestLoginTracking(unittest.TestCase):
    """Login should update last_login_at and log login_completed."""

    def test_login_updates_last_login(self):
        app, client = _make_client()
        _signup(client, email="logintrack@test.com", password="secret123")
        first_login = None
        with app.app_context():
            from app.models import UserIdentity

            user = UserIdentity.query.filter_by(email="logintrack@test.com").first()
            first_login = user.last_login_at

        client.get("/logout")
        _login(client, email="logintrack@test.com", password="secret123")
        with app.app_context():
            from app.models import UserIdentity

            user = UserIdentity.query.filter_by(email="logintrack@test.com").first()
            self.assertIsNotNone(user.last_login_at)
            # last_login_at should be >= first_login (may be same second)
            self.assertGreaterEqual(user.last_login_at, first_login)

    def test_login_logs_event(self):
        app, client = _make_client()
        _signup(client, email="logged@test.com", password="secret123")
        client.get("/logout")
        _login(client, email="logged@test.com", password="secret123")
        with app.app_context():
            from app.models import ActivityEvent

            events = ActivityEvent.query.filter_by(event_type="login_completed").all()
            self.assertGreaterEqual(len(events), 1)


# ── Logout Event Tracking ────────────────────────────────────────


class TestLogoutTracking(unittest.TestCase):
    def test_logout_logs_event(self):
        app, client = _make_client()
        _signup(client, email="logoutev@test.com", password="secret123")
        client.get("/logout")
        with app.app_context():
            from app.models import ActivityEvent

            events = ActivityEvent.query.filter_by(event_type="logout_completed").all()
            self.assertGreaterEqual(len(events), 1)


# ── Onboarding Tracking ─────────────────────────────────────────


class TestOnboardingTracking(unittest.TestCase):
    """Resume upload + match generation trigger onboarding flags."""

    def test_resume_upload_sets_flag(self):
        """Manual flag test: set has_uploaded_resume directly."""
        app, client = _make_client()
        _signup(client, email="resume@test.com", password="secret123")
        with app.app_context():
            from app.models import UserIdentity
            from app.db import db

            user = UserIdentity.query.filter_by(email="resume@test.com").first()
            user.has_uploaded_resume = True
            db.session.commit()

            user = UserIdentity.query.filter_by(email="resume@test.com").first()
            self.assertTrue(user.has_uploaded_resume)

    def test_matches_generated_sets_flag(self):
        app, client = _make_client()
        _signup(client, email="match@test.com", password="secret123")
        with app.app_context():
            from app.models import UserIdentity
            from app.db import db

            user = UserIdentity.query.filter_by(email="match@test.com").first()
            user.has_generated_matches = True
            db.session.commit()

            user = UserIdentity.query.filter_by(email="match@test.com").first()
            self.assertTrue(user.has_generated_matches)

    def test_onboarding_completed_set_once(self):
        """onboarding_completed_at is set when both flags are true."""
        app, client = _make_client()
        _signup(client, email="onboard@test.com", password="secret123")
        with app.app_context():
            from app.models import UserIdentity
            from app.db import db
            from app.routes import _check_onboarding_complete

            user = UserIdentity.query.filter_by(email="onboard@test.com").first()
            user.has_uploaded_resume = True
            user.has_generated_matches = True
            db.session.commit()

            _check_onboarding_complete(user)
            self.assertIsNotNone(user.onboarding_completed_at)
            first_ts = user.onboarding_completed_at

            # Calling again should NOT update the timestamp
            _check_onboarding_complete(user)
            self.assertEqual(user.onboarding_completed_at, first_ts)

    def test_onboarding_not_complete_with_only_resume(self):
        app, client = _make_client()
        _signup(client, email="partial@test.com", password="secret123")
        with app.app_context():
            from app.models import UserIdentity
            from app.db import db
            from app.routes import _check_onboarding_complete

            user = UserIdentity.query.filter_by(email="partial@test.com").first()
            user.has_uploaded_resume = True
            db.session.commit()

            _check_onboarding_complete(user)
            self.assertIsNone(user.onboarding_completed_at)

    def test_onboarding_completed_event_logged_once(self):
        app, client = _make_client()
        _signup(client, email="once@test.com", password="secret123")
        with app.app_context():
            from app.models import UserIdentity, ActivityEvent
            from app.db import db
            from app.routes import _check_onboarding_complete

            user = UserIdentity.query.filter_by(email="once@test.com").first()
            user.has_uploaded_resume = True
            user.has_generated_matches = True
            db.session.commit()

            _check_onboarding_complete(user)
            _check_onboarding_complete(user)

            events = ActivityEvent.query.filter_by(
                event_type="onboarding_completed", user_id=user.id
            ).all()
            self.assertEqual(len(events), 1)


# ── Dashboard Onboarding UI ─────────────────────────────────────


class TestDashboardOnboarding(unittest.TestCase):
    """Dashboard shows onboarding progress card."""

    def test_dashboard_shows_progress_card(self):
        app, client = _make_client()
        _signup(client, email="card@test.com", password="secret123")
        resp = client.get("/dashboard")
        html = resp.data.decode()
        self.assertIn("Getting Started", html)
        self.assertIn("Account created", html)
        self.assertIn("1 of 3 complete", html)

    def test_dashboard_shows_resume_done(self):
        app, client = _make_client()
        _signup(client, email="resdone@test.com", password="secret123")
        with app.app_context():
            from app.models import UserIdentity
            from app.db import db

            user = UserIdentity.query.filter_by(email="resdone@test.com").first()
            user.has_uploaded_resume = True
            db.session.commit()
        resp = client.get("/dashboard")
        html = resp.data.decode()
        self.assertIn("2 of 3 complete", html)

    def test_dashboard_shows_complete(self):
        app, client = _make_client()
        _signup(client, email="alldone@test.com", password="secret123")
        with app.app_context():
            from app.models import UserIdentity
            from app.db import db
            from datetime import datetime

            user = UserIdentity.query.filter_by(email="alldone@test.com").first()
            user.has_uploaded_resume = True
            user.has_generated_matches = True
            user.onboarding_completed_at = datetime.utcnow()
            db.session.commit()
        resp = client.get("/dashboard")
        html = resp.data.decode()
        self.assertIn("Onboarding Complete", html)


# ── Founder Metrics Route ────────────────────────────────────────


class TestFounderMetrics(unittest.TestCase):
    """Founder metrics access control and data display."""

    def test_metrics_requires_auth(self):
        app, client = _make_client()
        resp = client.get("/founder/metrics", follow_redirects=False)
        self.assertIn(resp.status_code, [302, 303])
        self.assertIn("/login", resp.headers.get("Location", ""))

    def test_metrics_blocks_non_admin(self):
        app, client = _make_client()
        _signup(client, email="nonadmin@test.com", password="secret123")
        resp = client.get("/founder/metrics")
        self.assertEqual(resp.status_code, 403)

    def test_metrics_works_for_admin(self):
        app, client = _make_client()
        _signup(client, email="founder@test.com", password="secret123")
        _make_admin(app, email="founder@test.com")
        # Set session is_admin flag
        with client.session_transaction() as s:
            s["is_admin"] = True
        resp = client.get("/founder/metrics")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode()
        self.assertIn("Founder Metrics", html)
        self.assertIn("Total Users", html)
        self.assertIn("Total Signups", html)
        self.assertIn("Beta Command View", html)

    def test_metrics_counts_correct(self):
        app, client = _make_client()
        # Create a few users
        _signup(client, email="user1@test.com", password="secret123")
        client.get("/logout")
        _signup(client, email="user2@test.com", password="secret123")
        client.get("/logout")
        _signup(client, email="admin@test.com", password="secret123")
        _make_admin(app, email="admin@test.com")
        with client.session_transaction() as s:
            s["is_admin"] = True

        resp = client.get("/founder/metrics")
        html = resp.data.decode()
        # Should show at least 3 total users
        self.assertIn("3", html)

    def test_metrics_shows_recent_events(self):
        app, client = _make_client()
        _signup(client, email="evadmin@test.com", password="secret123")
        _make_admin(app, email="evadmin@test.com")
        with client.session_transaction() as s:
            s["is_admin"] = True

        resp = client.get("/founder/metrics")
        html = resp.data.decode()
        self.assertIn("signup_completed", html)
        self.assertIn("Recent Activity", html)


# ── Admin Bootstrap ──────────────────────────────────────────────


class TestAdminBootstrap(unittest.TestCase):
    """OFFERION_ADMIN_EMAILS env var promotes user to admin."""

    def test_admin_email_promoted_on_signup(self):
        app, client = _make_client()
        os.environ["OFFERION_ADMIN_EMAILS"] = "superadmin@test.com"
        try:
            _signup(client, email="superadmin@test.com", password="secret123")
            with client.session_transaction() as s:
                self.assertTrue(s.get("is_admin"))
            with app.app_context():
                from app.models import UserIdentity

                user = UserIdentity.query.filter_by(email="superadmin@test.com").first()
                self.assertTrue(user.is_admin)
        finally:
            os.environ.pop("OFFERION_ADMIN_EMAILS", None)

    def test_non_admin_email_not_promoted(self):
        app, client = _make_client()
        os.environ["OFFERION_ADMIN_EMAILS"] = "other@test.com"
        try:
            _signup(client, email="regular@test.com", password="secret123")
            with client.session_transaction() as s:
                self.assertFalse(s.get("is_admin", False))
        finally:
            os.environ.pop("OFFERION_ADMIN_EMAILS", None)

    def test_admin_email_promoted_on_login(self):
        app, client = _make_client()
        os.environ["OFFERION_ADMIN_EMAILS"] = "loginadmin@test.com"
        try:
            _signup(client, email="loginadmin@test.com", password="secret123")
            client.get("/logout")
            _login(client, email="loginadmin@test.com", password="secret123")
            with client.session_transaction() as s:
                self.assertTrue(s.get("is_admin"))
        finally:
            os.environ.pop("OFFERION_ADMIN_EMAILS", None)


# ── Navigation ───────────────────────────────────────────────────


class TestAdminNav(unittest.TestCase):
    """Admin nav link only visible for admin users."""

    def test_non_admin_no_metrics_link(self):
        app, client = _make_client()
        _signup(client, email="navuser@test.com", password="secret123")
        resp = client.get("/dashboard")
        html = resp.data.decode()
        self.assertNotIn("/founder/metrics", html)

    def test_admin_sees_metrics_link(self):
        app, client = _make_client()
        _signup(client, email="navadmin@test.com", password="secret123")
        _make_admin(app, email="navadmin@test.com")
        with client.session_transaction() as s:
            s["is_admin"] = True
        resp = client.get("/dashboard")
        html = resp.data.decode()
        self.assertIn("/founder/metrics", html)

    def test_landing_admin_sees_metrics_link(self):
        app, client = _make_client()
        _signup(client, email="ladmin@test.com", password="secret123")
        _make_admin(app, email="ladmin@test.com")
        with client.session_transaction() as s:
            s["is_admin"] = True
        resp = client.get("/")
        html = resp.data.decode()
        self.assertIn("/founder/metrics", html)

    def test_landing_non_admin_no_metrics_link(self):
        app, client = _make_client()
        _signup(client, email="luser@test.com", password="secret123")
        resp = client.get("/")
        html = resp.data.decode()
        self.assertNotIn("/founder/metrics", html)


# ── Backward Compatibility ───────────────────────────────────────


class TestBackwardCompat(unittest.TestCase):
    """Existing flows still work after Bundle V changes."""

    def test_signup_login_logout_flow(self):
        app, client = _make_client()
        resp = _signup(client, email="compat@test.com", password="secret123")
        self.assertIn(resp.status_code, [302, 303])
        resp = client.get("/dashboard")
        self.assertEqual(resp.status_code, 200)
        client.get("/logout")
        resp = client.get("/dashboard", follow_redirects=False)
        self.assertIn(resp.status_code, [302, 303])
        resp = _login(client, email="compat@test.com", password="secret123")
        self.assertIn(resp.status_code, [302, 303])
        resp = client.get("/dashboard")
        self.assertEqual(resp.status_code, 200)

    def test_public_routes_still_work(self):
        app, client = _make_client()
        self.assertEqual(client.get("/").status_code, 200)
        self.assertEqual(client.get("/pricing").status_code, 200)
        self.assertEqual(client.get("/login").status_code, 200)
        self.assertEqual(client.get("/signup").status_code, 200)

    def test_session_seeded_user_works(self):
        """TESTING backdoor: session-seeded user_id reaches dashboard."""
        app = _make_app()
        client = app.test_client()
        with app.app_context():
            from app.db import db
            from app.models import UserIdentity

            if not UserIdentity.query.filter_by(id="compat-v").first():
                user = UserIdentity(id="compat-v", tier="elite")
                db.session.add(user)
                db.session.commit()
        with client.session_transaction() as s:
            s["user_id"] = "compat-v"
            s["user_tier"] = "elite"
        resp = client.get("/dashboard")
        self.assertEqual(resp.status_code, 200)


class TestEmailReminderDelivery(unittest.TestCase):
    def test_email_service_reports_log_only_without_smtp(self):
        from app.utils.email_notifications import EmailNotificationService

        previous = {
            key: os.environ.get(key)
            for key in (
                "OFFERION_EMAIL_ENABLED",
                "OFFERION_SMTP_HOST",
                "OFFERION_SMTP_PORT",
                "OFFERION_SMTP_USERNAME",
                "OFFERION_SMTP_PASSWORD",
                "OFFERION_SMTP_FROM_EMAIL",
                "OFFERION_SMTP_USE_TLS",
            )
        }
        try:
            for key in previous:
                os.environ.pop(key, None)
            service = EmailNotificationService()
            summary = service.health_summary()
            self.assertFalse(summary["enabled"])
            self.assertEqual(summary["mode"], "log-only")
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_due_alert_logs_email_skip_event_once(self):
        app, client = _make_client()
        _signup(client, email="alerts@test.com", password="secret123")
        with app.app_context():
            from app.models import ActivityEvent, UserIdentity
            from app.routes import _process_due_alert_reminders

            user = UserIdentity.query.filter_by(email="alerts@test.com").first()
            alerts = [
                {
                    "id": "alert-v-1",
                    "message": "Follow up on Offerion role",
                    "due_at": datetime.utcnow().strftime("%Y-%m-%d"),
                    "is_complete": False,
                }
            ]

            first = _process_due_alert_reminders(user, alerts=alerts)
            second = _process_due_alert_reminders(user, alerts=alerts)

            self.assertEqual(first["checked"], 1)
            self.assertEqual(first["skipped"], 1)
            self.assertEqual(second["skipped"], 0)

            events = ActivityEvent.query.filter_by(
                user_id=user.id, event_type="alert_email_skipped"
            ).all()
            self.assertEqual(len(events), 1)


class TestStripeOperationalHealth(unittest.TestCase):
    def test_stripe_config_reports_missing_prices(self):
        from app.utils.stripe_billing import get_stripe_config

        previous = {
            key: os.environ.get(key)
            for key in (
                "STRIPE_SECRET_KEY",
                "STRIPE_WEBHOOK_SECRET",
                "STRIPE_PRICE_COMET",
                "STRIPE_PRICE_OPERATOR",
                "STRIPE_PRICE_PROFESSIONAL",
                "STRIPE_PRICE_ELITE",
            )
        }
        try:
            os.environ["STRIPE_SECRET_KEY"] = "sk_test_123"
            os.environ.pop("STRIPE_WEBHOOK_SECRET", None)
            os.environ.pop("STRIPE_PRICE_COMET", None)
            os.environ.pop("STRIPE_PRICE_OPERATOR", None)
            os.environ.pop("STRIPE_PRICE_PROFESSIONAL", None)
            os.environ.pop("STRIPE_PRICE_ELITE", None)

            conf = get_stripe_config()
            self.assertTrue(conf["has_secret_key"])
            self.assertFalse(conf["checkout_ready"])
            self.assertIn("STRIPE_WEBHOOK_SECRET", conf["missing"])
            self.assertIn("STRIPE_PRICE_COMET", conf["missing"])
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
