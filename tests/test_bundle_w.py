"""Tests for Bundle W — Trial Enforcement + Usage Limits + Upgrade Triggers."""

import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_app(**env_overrides):
    _prev = {}
    for k in ("DATABASE_URL", "OFFERION_PAID_EMAILS", "OFFERION_ADMIN_EMAILS"):
        _prev[k] = os.environ.get(k)
    os.environ["DATABASE_URL"] = "sqlite://"
    for k, v in env_overrides.items():
        os.environ[k] = v
    try:
        from app import create_app

        app = create_app(testing=True)
    finally:
        for k, prev_val in _prev.items():
            if k in env_overrides:
                if prev_val is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = prev_val
            elif prev_val is None:
                os.environ.pop(k, None)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    return app


def _make_client(**env_overrides):
    app = _make_app(**env_overrides)
    return app, app.test_client()


def _signup(client, email="w_test@example.com", password="password123"):
    return client.post(
        "/signup",
        data={"email": email, "password": password},
        follow_redirects=False,
    )


def _login(client, email="w_test@example.com", password="password123"):
    return client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=False,
    )


def _get_user(app, email="w_test@example.com"):
    with app.app_context():
        from app.models import UserIdentity

        return UserIdentity.query.filter_by(email=email).first()


# ── Billing helper unit tests ─────────────────────────────────────


class TestBillingHelpers(unittest.TestCase):
    """Test app/utils/billing.py functions in isolation."""

    def setUp(self):
        self.app = _make_app()
        self.ctx = self.app.app_context()
        self.ctx.push()
        from app.models import UserIdentity
        from app.db import db

        self.user = UserIdentity(email="billing@test.com")
        db.session.add(self.user)
        db.session.commit()

    def tearDown(self):
        self.ctx.pop()

    def test_new_trial_user_plan_state(self):
        from app.utils.tier_config import start_trial
        from app.utils.billing import get_user_plan_state

        start_trial(self.user)
        self.assertEqual(get_user_plan_state(self.user), "trial")

    def test_expired_trial_becomes_free(self):
        from app.utils.tier_config import start_trial
        from app.utils.billing import get_user_plan_state

        start_trial(self.user)
        # Simulate expired trial
        self.user.trial_end = datetime.utcnow() - timedelta(days=1)
        self.assertEqual(get_user_plan_state(self.user), "free")

    def test_paid_user_plan_state(self):
        from app.utils.billing import get_user_plan_state

        self.user.subscription_status = "active"
        self.assertEqual(get_user_plan_state(self.user), "paid")

    def test_free_analysis_limit(self):
        from app.utils.billing import can_run_resume_analysis

        self.user.tier = "free"
        self.user.monthly_resume_analyses_used = 0
        self.assertTrue(can_run_resume_analysis(self.user))
        self.user.monthly_resume_analyses_used = 2
        self.assertFalse(can_run_resume_analysis(self.user))

    def test_trial_analysis_limit(self):
        from app.utils.tier_config import start_trial
        from app.utils.billing import can_run_resume_analysis

        start_trial(self.user)
        self.user.monthly_resume_analyses_used = 9
        self.assertTrue(can_run_resume_analysis(self.user))
        self.user.monthly_resume_analyses_used = 10
        self.assertFalse(can_run_resume_analysis(self.user))

    def test_paid_bypasses_limits(self):
        from app.utils.billing import (
            can_run_resume_analysis,
            can_view_jobs,
            can_download_tailored_resume,
            can_download_report,
        )

        self.user.subscription_status = "active"
        self.user.monthly_resume_analyses_used = 999
        self.user.monthly_job_views_used = 999
        self.assertTrue(can_run_resume_analysis(self.user))
        self.assertTrue(can_view_jobs(self.user))
        self.assertTrue(can_download_tailored_resume(self.user))
        self.assertTrue(can_download_report(self.user))

    def test_free_job_view_limit(self):
        from app.utils.billing import can_view_jobs

        self.user.tier = "free"
        self.user.monthly_job_views_used = 9
        self.assertTrue(can_view_jobs(self.user))
        self.user.monthly_job_views_used = 10
        self.assertFalse(can_view_jobs(self.user))

    def test_free_tailored_resume_blocked(self):
        from app.utils.billing import can_download_tailored_resume

        self.user.tier = "free"
        self.assertFalse(can_download_tailored_resume(self.user))

    def test_trial_tailored_resume_allowed(self):
        from app.utils.tier_config import start_trial
        from app.utils.billing import can_download_tailored_resume

        start_trial(self.user)
        self.assertTrue(can_download_tailored_resume(self.user))

    def test_free_report_download_limited(self):
        from app.utils.billing import can_download_report

        self.user.tier = "free"
        self.user.monthly_resume_downloads_used = 0
        self.assertTrue(can_download_report(self.user))
        self.user.monthly_resume_downloads_used = 1
        self.assertFalse(can_download_report(self.user))

    def test_monthly_reset_works(self):
        from app.utils.billing import reset_monthly_usage_if_needed

        self.user.tier = "free"
        self.user.monthly_resume_analyses_used = 5
        self.user.monthly_job_views_used = 50
        self.user.monthly_resume_downloads_used = 3
        # Set reset_at to last month
        last_month = datetime.utcnow() - timedelta(days=35)
        self.user.usage_reset_at = last_month

        reset_monthly_usage_if_needed(self.user)
        self.assertEqual(self.user.monthly_resume_analyses_used, 0)
        self.assertEqual(self.user.monthly_job_views_used, 0)
        self.assertEqual(self.user.monthly_resume_downloads_used, 0)
        self.assertIsNotNone(self.user.usage_reset_at)

    def test_no_reset_same_month(self):
        from app.utils.billing import reset_monthly_usage_if_needed

        self.user.monthly_resume_analyses_used = 1
        self.user.usage_reset_at = datetime.utcnow()

        reset_monthly_usage_if_needed(self.user)
        self.assertEqual(self.user.monthly_resume_analyses_used, 1)

    def test_record_usage_increments(self):
        from app.utils.billing import (
            record_resume_analysis_usage,
            record_job_view_usage,
            record_resume_download_usage,
        )

        self.user.monthly_resume_analyses_used = 0
        self.user.monthly_job_views_used = 0
        self.user.monthly_resume_downloads_used = 0
        self.user.usage_reset_at = datetime.utcnow()

        record_resume_analysis_usage(self.user)
        self.assertEqual(self.user.monthly_resume_analyses_used, 1)

        record_job_view_usage(self.user, count=5)
        self.assertEqual(self.user.monthly_job_views_used, 5)

        record_resume_download_usage(self.user)
        self.assertEqual(self.user.monthly_resume_downloads_used, 1)

    def test_get_upgrade_reason(self):
        from app.utils.billing import get_upgrade_reason

        self.user.tier = "free"
        self.user.monthly_resume_analyses_used = 5
        self.user.usage_reset_at = datetime.utcnow()
        reason = get_upgrade_reason(self.user, "resume_analysis")
        self.assertIn("free limit", reason)

    def test_get_upgrade_reason_paid_none(self):
        from app.utils.billing import get_upgrade_reason

        self.user.subscription_status = "active"
        reason = get_upgrade_reason(self.user, "resume_analysis")
        self.assertIsNone(reason)

    def test_usage_summary_free(self):
        from app.utils.billing import get_usage_summary

        self.user.tier = "free"
        self.user.monthly_resume_analyses_used = 1
        self.user.usage_reset_at = datetime.utcnow()
        summary = get_usage_summary(self.user)
        self.assertEqual(summary["plan"], "free")
        self.assertEqual(summary["analyses_used"], 1)
        self.assertEqual(summary["analyses_limit"], 2)
        self.assertFalse(summary["can_download_tailored"])

    def test_usage_summary_paid(self):
        from app.utils.billing import get_usage_summary

        self.user.subscription_status = "active"
        summary = get_usage_summary(self.user)
        self.assertEqual(summary["plan"], "paid")
        self.assertIsNone(summary["analyses_limit"])
        self.assertTrue(summary["can_download_tailored"])


# ── Env-based paid activation ─────────────────────────────────────


class TestPaidEmailActivation(unittest.TestCase):
    def test_sync_sets_paid(self):
        app = _make_app()
        with app.app_context():
            from app.models import UserIdentity
            from app.db import db
            from app.utils.billing import sync_paid_status

            user = UserIdentity(email="vip@test.com", tier="free")
            db.session.add(user)
            db.session.commit()

            with patch.dict(
                os.environ, {"OFFERION_PAID_EMAILS": "vip@test.com,another@test.com"}
            ):
                result = sync_paid_status(user)
            self.assertTrue(result)
            self.assertEqual(user.subscription_status, "active")
            self.assertIsNotNone(user.paid_started_at)

    def test_sync_does_not_set_nonlisted(self):
        app = _make_app()
        with app.app_context():
            from app.models import UserIdentity
            from app.db import db
            from app.utils.billing import sync_paid_status

            user = UserIdentity(email="nobody@test.com", tier="free")
            db.session.add(user)
            db.session.commit()

            with patch.dict(os.environ, {"OFFERION_PAID_EMAILS": "vip@test.com"}):
                result = sync_paid_status(user)
            self.assertFalse(result)
            self.assertIsNone(user.subscription_status)

    def test_paid_email_login_flow(self):
        app, client = _make_client()
        with client:
            _signup(client, email="paidlogin@test.com")
            # Log out and back in with env var set
            client.get("/logout")
            with patch.dict(os.environ, {"OFFERION_PAID_EMAILS": "paidlogin@test.com"}):
                _login(client, email="paidlogin@test.com")
                # Access dashboard to trigger bootstrap sync
                client.get("/dashboard", follow_redirects=True)
            with app.app_context():
                from app.models import UserIdentity

                user = UserIdentity.query.filter_by(email="paidlogin@test.com").first()
                self.assertEqual(user.subscription_status, "active")


# ── Signup creates trial ──────────────────────────────────────────


class TestSignupTrial(unittest.TestCase):
    def test_new_signup_starts_trial(self):
        app, client = _make_client()
        with client:
            resp = _signup(client)
            self.assertIn(resp.status_code, (302, 303))
            with app.app_context():
                user = _get_user(app)
                self.assertIsNotNone(user)
                self.assertEqual(user.tier, "trial")
                self.assertIsNotNone(user.trial_start)
                self.assertIsNotNone(user.trial_end)
                delta = user.trial_end - user.trial_start
                self.assertGreaterEqual(delta.days, 6)

    def test_trial_started_event_logged(self):
        app, client = _make_client()
        with client:
            _signup(client)
            with app.app_context():
                from app.models import ActivityEvent

                events = ActivityEvent.query.filter_by(event_type="trial_started").all()
                self.assertGreaterEqual(len(events), 1)


# ── Trial expiry ──────────────────────────────────────────────────


class TestTrialExpiry(unittest.TestCase):
    def test_expired_trial_downgrades_on_request(self):
        app, client = _make_client()
        with client:
            _signup(client, email="expire@test.com")
            # Simulate expired trial
            with app.app_context():
                from app.models import UserIdentity
                from app.db import db

                user = UserIdentity.query.filter_by(email="expire@test.com").first()
                user.trial_end = datetime.utcnow() - timedelta(days=1)
                db.session.commit()
            # Next request triggers bootstrap which checks expiry
            resp = client.get("/dashboard", follow_redirects=True)
            self.assertEqual(resp.status_code, 200)
            with app.app_context():
                from app.models import UserIdentity

                user = UserIdentity.query.filter_by(email="expire@test.com").first()
                self.assertEqual(user.tier, "free")


# ── Route-level enforcement ───────────────────────────────────────


class TestRouteEnforcement(unittest.TestCase):
    def _setup_user(self, app, client, email="enforce@test.com", tier="free"):
        _signup(client, email=email)
        with app.app_context():
            from app.models import UserIdentity
            from app.db import db

            user = UserIdentity.query.filter_by(email=email).first()
            if tier == "free":
                user.tier = "free"
                user.trial_end = datetime.utcnow() - timedelta(days=1)
            elif tier == "paid":
                user.subscription_status = "active"
            db.session.commit()

    def test_free_analysis_limit_blocks(self):
        """Free user hitting analysis limit gets error instead of processing."""
        app, client = _make_client()
        with client:
            self._setup_user(app, client, email="freeblock@test.com", tier="free")
            # Set usage to limit
            with app.app_context():
                from app.models import UserIdentity
                from app.db import db

                user = UserIdentity.query.filter_by(email="freeblock@test.com").first()
                user.monthly_resume_analyses_used = 2
                user.usage_reset_at = datetime.utcnow()
                db.session.commit()

            # Try to upload a resume — should get error message
            import io

            data = {
                "resume": (io.BytesIO(b"test resume content"), "resume.pdf"),
            }
            resp = client.post(
                "/dashboard",
                data=data,
                follow_redirects=True,
                content_type="multipart/form-data",
            )
            self.assertEqual(resp.status_code, 200)
            self.assertIn(b"limit", resp.data.lower())

    def test_free_report_download_limited(self):
        """Free user can download report once, second time redirects."""
        app, client = _make_client()
        with client:
            self._setup_user(app, client, email="reportlimit@test.com", tier="free")
            # Set usage counter to 1 (limit already hit)
            with app.app_context():
                from app.models import UserIdentity
                from app.db import db

                user = UserIdentity.query.filter_by(
                    email="reportlimit@test.com"
                ).first()
                user.monthly_resume_downloads_used = 1
                user.usage_reset_at = datetime.utcnow()
                db.session.commit()

            resp = client.get("/download-report", follow_redirects=False)
            # Should redirect to pricing
            self.assertEqual(resp.status_code, 302)
            self.assertIn("/pricing", resp.headers.get("Location", ""))

    def test_free_tailored_download_blocked(self):
        """Free user cannot download tailored brief."""
        app, client = _make_client()
        with client:
            self._setup_user(app, client, email="notailored@test.com", tier="free")
            resp = client.get("/download-tailored-brief", follow_redirects=False)
            self.assertEqual(resp.status_code, 302)
            self.assertIn("/pricing", resp.headers.get("Location", ""))

    def test_trial_tailored_download_allowed(self):
        """Trial user can download tailored brief (will get 400 without report data)."""
        app, client = _make_client()
        with client:
            _signup(client, email="trialdl@test.com")
            # trial user tries to download — no report data → 400 but not redirected
            resp = client.get("/download-tailored-brief", follow_redirects=False)
            # Should NOT redirect to pricing (trial allows it)
            self.assertNotEqual(resp.status_code, 302)

    def test_paid_user_bypasses_all_limits(self):
        """Paid user gets through even with high usage."""
        app, client = _make_client()
        with client:
            self._setup_user(app, client, email="paidbypass@test.com", tier="paid")
            with app.app_context():
                from app.models import UserIdentity
                from app.db import db

                user = UserIdentity.query.filter_by(email="paidbypass@test.com").first()
                user.monthly_resume_analyses_used = 100
                user.monthly_resume_downloads_used = 100
                user.usage_reset_at = datetime.utcnow()
                db.session.commit()

            # Report download should proceed (400 because no report data, not 302)
            resp = client.get("/download-report", follow_redirects=False)
            self.assertNotEqual(resp.status_code, 302)

            # Tailored download should proceed
            resp = client.get("/download-tailored-brief", follow_redirects=False)
            self.assertNotEqual(resp.status_code, 302)


# ── Dashboard billing UI ─────────────────────────────────────────


class TestDashboardBillingUI(unittest.TestCase):
    def test_billing_card_shown(self):
        """Dashboard shows the billing status card with counters."""
        app, client = _make_client()
        with client:
            _signup(client, email="billui@test.com")
            resp = client.get("/dashboard", follow_redirects=True)
            self.assertEqual(resp.status_code, 200)
            html = resp.data.decode()
            self.assertIn("billing-status-card", html)
            self.assertIn("Analyses:", html)
            self.assertIn("Job views:", html)
            self.assertIn("Downloads:", html)

    def test_trial_badge_on_dashboard(self):
        """Trial user sees trial badge."""
        app, client = _make_client()
        with client:
            _signup(client, email="trialbadge@test.com")
            resp = client.get("/dashboard", follow_redirects=True)
            html = resp.data.decode()
            self.assertIn("tier-badge", html)
            self.assertIn("TRIAL", html)

    def test_jobs_capped_message_shown(self):
        """When job views exhausted, capped message appears."""
        app, client = _make_client()
        with client:
            _signup(client, email="jobcap@test.com")
            # Expire trial so user is free with exhausted view quota
            with app.app_context():
                from app.models import UserIdentity
                from app.db import db

                user = UserIdentity.query.filter_by(email="jobcap@test.com").first()
                user.tier = "free"
                user.trial_end = datetime.utcnow() - timedelta(days=1)
                user.monthly_job_views_used = 10
                user.usage_reset_at = datetime.utcnow()
                db.session.commit()

            # Need report_data in session for jobs to render
            with client.session_transaction() as sess:
                sess["report_data"] = {
                    "result": {"filename": "test.pdf", "status": "extracted"},
                    "profile": {"skills": ["python"]},
                    "match": {"target_role": "Dev", "score": 80},
                    "suggestions": None,
                    "feedback": None,
                    "jd_comparison": None,
                    "rewrite": None,
                    "scorecard": None,
                    "tailored": None,
                    "action_plan": None,
                }

            resp = client.get("/dashboard", follow_redirects=True)
            html = resp.data.decode()
            self.assertIn("job view limit", html)
            self.assertIn("Upgrade to continue", html)

    def test_upgrade_prompt_on_limit_hit_error(self):
        """When analysis limit hit, error contains upgrade info."""
        app, client = _make_client()
        with client:
            _signup(client, email="upgprompt@test.com")
            with app.app_context():
                from app.models import UserIdentity
                from app.db import db

                user = UserIdentity.query.filter_by(email="upgprompt@test.com").first()
                user.tier = "free"
                user.trial_end = datetime.utcnow() - timedelta(days=1)
                user.monthly_resume_analyses_used = 2
                user.usage_reset_at = datetime.utcnow()
                db.session.commit()

            import io

            data = {
                "resume": (io.BytesIO(b"test resume content"), "resume.pdf"),
            }
            resp = client.post(
                "/dashboard",
                data=data,
                follow_redirects=True,
                content_type="multipart/form-data",
            )
            html = resp.data.decode()
            self.assertIn("limit", html.lower())


# ── Pricing page ──────────────────────────────────────────────────


class TestPricingPage(unittest.TestCase):
    def test_pricing_shows_enforcement_note(self):
        app, client = _make_client()
        with client:
            _signup(client, email="pricenote@test.com")
            resp = client.get("/pricing")
            html = resp.data.decode()
            self.assertIn("Current Launch Plan", html)
            self.assertIn("2 analyses", html)
            self.assertIn("10 job views", html)


# ── Blocked actions fail gracefully ───────────────────────────────


class TestGracefulBlocking(unittest.TestCase):
    def test_blocked_download_no_crash(self):
        """Blocked download redirects, doesn't crash."""
        app, client = _make_client()
        with client:
            _signup(client, email="nocrash@test.com")
            with app.app_context():
                from app.models import UserIdentity
                from app.db import db

                user = UserIdentity.query.filter_by(email="nocrash@test.com").first()
                user.tier = "free"
                user.trial_end = datetime.utcnow() - timedelta(days=1)
                db.session.commit()

            resp = client.get("/download-tailored-brief", follow_redirects=True)
            self.assertEqual(resp.status_code, 200)
            # Should be on pricing page
            html = resp.data.decode()
            self.assertIn("Choose Your Plan", html)


# ── Model fields exist ────────────────────────────────────────────


class TestModelFields(unittest.TestCase):
    def test_new_fields_exist(self):
        app = _make_app()
        with app.app_context():
            from app.models import UserIdentity
            from app.db import db

            user = UserIdentity(email="fields@test.com")
            db.session.add(user)
            db.session.commit()

            self.assertTrue(hasattr(user, "subscription_status"))
            self.assertTrue(hasattr(user, "paid_started_at"))
            self.assertTrue(hasattr(user, "monthly_resume_analyses_used"))
            self.assertTrue(hasattr(user, "monthly_job_views_used"))
            self.assertTrue(hasattr(user, "monthly_resume_downloads_used"))
            self.assertTrue(hasattr(user, "usage_reset_at"))
            self.assertTrue(hasattr(user, "hard_gated_at"))
            self.assertTrue(hasattr(user, "last_upgrade_prompt_at"))

            # Defaults
            self.assertEqual(user.monthly_resume_analyses_used, 0)
            self.assertEqual(user.monthly_job_views_used, 0)
            self.assertEqual(user.monthly_resume_downloads_used, 0)
            self.assertIsNone(user.subscription_status)
            self.assertIsNone(user.paid_started_at)


# ── Backward compatibility ────────────────────────────────────────


class TestBackwardCompat(unittest.TestCase):
    def test_existing_auth_flow_unbroken(self):
        """Signup + login + logout still works."""
        app, client = _make_client()
        with client:
            resp = _signup(client, email="compat@test.com")
            self.assertIn(resp.status_code, (302, 303))
            client.get("/logout")
            resp = _login(client, email="compat@test.com")
            self.assertIn(resp.status_code, (302, 303))
            resp = client.get("/dashboard", follow_redirects=True)
            self.assertEqual(resp.status_code, 200)

    def test_onboarding_still_works(self):
        """Onboarding progress card still appears."""
        app, client = _make_client()
        with client:
            _signup(client, email="onboard_compat@test.com")
            resp = client.get("/dashboard", follow_redirects=True)
            html = resp.data.decode()
            self.assertIn("onboarding-progress-card", html)


if __name__ == "__main__":
    unittest.main()
