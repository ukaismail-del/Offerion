"""Tests for Bundle S — User Readiness + Release Flow + Pricing/Trial Engine."""

import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Shared fixtures ──────────────────────────────────────────────

_PROFILE = {"skills": ["python", "sql", "flask"], "name": "Test User"}
_MATCH = {
    "target_role": "Backend Developer",
    "score": 72,
    "level": "Strong",
    "matched": ["python"],
    "missing": ["docker"],
    "keywords_entered": "python",
    "explanation": "Good match.",
}
_TAILORED = {
    "target_title": "Backend Dev",
    "skills_to_feature": [{"skill": "python"}],
    "professional_summary": ["Experienced dev"],
    "experience_focus_points": ["APIs"],
}
_ENHANCED = {
    "name": "Test User",
    "contact": "test@example.com",
    "target_title": "Backend Dev",
    "enhanced_summary": "Experienced dev",
    "enhanced_skills": ["Python", "Flask"],
    "enhanced_experience_bullets": ["Built APIs"],
    "enhanced_education": ["BS CS"],
    "ats_alignment_notes": ["Good ATS"],
    "targeting": {
        "mode": "job-targeted",
        "job_title": "Backend Dev",
        "company": "Acme",
        "matched": ["python", "flask"],
        "omitted": ["docker"],
        "emphasized": ["APIs"],
    },
}


def _make_client(tier="elite"):
    from app import create_app
    from app.db import db
    from app.models import UserIdentity

    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    client = app.test_client()

    with app.app_context():
        existing = UserIdentity.query.filter_by(id="test-user-s").first()
        if existing:
            existing.tier = tier
            db.session.commit()
        else:
            user = UserIdentity(id="test-user-s", tier=tier)
            db.session.add(user)
            db.session.commit()

    return app, client


def _seed_session(client, report_data=None, enhanced=None, tier="elite"):
    """Seed session with test data via the test client."""
    with client.session_transaction() as sess:
        sess["user_id"] = "test-user-s"
        sess["user_tier"] = tier
        if report_data:
            sess["report_data"] = report_data
        if enhanced:
            sess["enhanced_resume"] = enhanced


# ── M111 — First-Run Guidance Tests ─────────────────────────────


class TestM111FirstRunGuidance(unittest.TestCase):
    """Dashboard and resume preview show guidance for first-time users."""

    def test_dashboard_empty_state_returns_200(self):
        app, client = _make_client()
        with client.session_transaction() as sess:
            sess["user_id"] = "test-user-s"
            sess["user_tier"] = "elite"
        resp = client.get("/dashboard")
        self.assertEqual(resp.status_code, 200)

    def test_dashboard_empty_state_shows_guidance(self):
        app, client = _make_client()
        with client.session_transaction() as sess:
            sess["user_id"] = "test-user-s"
            sess["user_tier"] = "elite"
        resp = client.get("/dashboard")
        html = resp.data.decode()
        self.assertIn("first-run-guidance", html)
        self.assertIn("Upload your resume", html)

    def test_dashboard_populated_returns_200(self):
        app, client = _make_client()
        _seed_session(client, report_data={"profile": _PROFILE, "match": _MATCH})
        resp = client.get("/dashboard")
        self.assertEqual(resp.status_code, 200)

    def test_resume_preview_no_report_renders_safely(self):
        """M113: resume preview without report_data shows empty state instead of crashing."""
        app, client = _make_client()
        with client.session_transaction() as sess:
            sess["user_id"] = "test-user-s"
            sess["user_tier"] = "elite"
        resp = client.get("/resume-preview")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode()
        self.assertIn("No resume analyzed yet", html)
        self.assertIn("dashboard", html.lower())


# ── M112 — Loading/Processing Feedback Tests ────────────────────


class TestM112LoadingFeedback(unittest.TestCase):
    """Loading indicators exist in rendered templates."""

    def test_dashboard_has_loading_js(self):
        app, client = _make_client()
        _seed_session(client, report_data={"profile": _PROFILE, "match": _MATCH})
        resp = client.get("/dashboard")
        html = resp.data.decode()
        # Dashboard should expose visible loading triggers in a normal in-progress state
        self.assertIn("btn-loading-trigger", html)
        self.assertIn("offerionLoading", html)

    def test_resume_preview_has_loading_triggers(self):
        app, client = _make_client()
        _seed_session(client, report_data={"profile": _PROFILE, "match": _MATCH})
        resp = client.get("/resume-preview")
        html = resp.data.decode()
        self.assertIn("btn-loading-trigger", html)

    def test_loading_css_class_in_stylesheet(self):
        app, client = _make_client()
        resp = client.get("/static/styles.css")
        css = resp.data.decode()
        self.assertIn("is-loading", css)
        self.assertIn("offerion-spin", css)


# ── M113 — Safer Error States Tests ─────────────────────────────


class TestM113ErrorStates(unittest.TestCase):
    """Graceful handling of missing data and stale packages."""

    def test_stale_package_recovery_message(self):
        """Opening a partial package shows recovery guidance instead of crashing."""
        app, client = _make_client()
        with client.session_transaction() as sess:
            sess["user_id"] = "test-user-s"
            sess["user_tier"] = "elite"
            sess["application_packages"] = [
                {
                    "id": "stale-pkg",
                    "label": "Old Package",
                    "target_title": "Dev",
                    "company": "Co",
                    "created_at": "2025-01-01",
                    "report_data": None,  # corrupt/missing
                    "enhanced_resume": None,
                    "cover_letter_draft": None,
                    "enhanced_cover_letter": None,
                }
            ]
        resp = client.get("/application-package/stale-pkg", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode()
        self.assertIn("partial data", html)
        self.assertIn("rebuild a fresh package", html)

    def test_missing_report_data_safe_render(self):
        """Dashboard with no report_data still renders."""
        app, client = _make_client()
        with client.session_transaction() as sess:
            sess["user_id"] = "test-user-s"
            sess["user_tier"] = "elite"
            sess.pop("report_data", None)
        resp = client.get("/dashboard")
        self.assertEqual(resp.status_code, 200)

    def test_resume_preview_partial_data_safe(self):
        """Resume preview with minimal report_data renders safely."""
        app, client = _make_client()
        _seed_session(client, report_data={"profile": _PROFILE})
        resp = client.get("/resume-preview")
        self.assertEqual(resp.status_code, 200)


# ── M114 — Tier Value Clarity Tests ──────────────────────────────


class TestM114TierClarity(unittest.TestCase):
    """Tier and value messaging renders correctly."""

    def test_pricing_page_shows_value_clarity(self):
        app, client = _make_client()
        with client.session_transaction() as sess:
            sess["user_id"] = "test-user-s"
            sess["user_tier"] = "free"
        resp = client.get("/pricing")
        html = resp.data.decode()
        self.assertIn("Why upgrade?", html)

    def test_pricing_page_hides_trial_from_plans(self):
        """Trial should not appear as a purchasable plan."""
        app, client = _make_client()
        with client.session_transaction() as sess:
            sess["user_id"] = "test-user-s"
            sess["user_tier"] = "free"
        resp = client.get("/pricing")
        html = resp.data.decode()
        # "Trial" tier card should NOT be shown as a purchasable tier
        self.assertNotIn('href="/upgrade/trial"', html)

    def test_pricing_page_shows_trial_banner_for_trial_user(self):
        from app.db import db
        from app.models import UserIdentity
        from app.utils.tier_config import start_trial

        app, client = _make_client(tier="trial")
        with app.app_context():
            user = UserIdentity.query.filter_by(id="test-user-s").first()
            if user:
                start_trial(user)
                db.session.commit()
        with client.session_transaction() as sess:
            sess["user_id"] = "test-user-s"
            sess["user_tier"] = "trial"
            sess["trial_days_left"] = 5
        resp = client.get("/pricing")
        html = resp.data.decode()
        self.assertIn("trial-banner", html)
        self.assertIn("Unlocked in Trial", html)

    def test_job_detail_no_resume_guidance(self):
        app, client = _make_client()
        with client.session_transaction() as sess:
            sess["user_id"] = "test-user-s"
            sess["user_tier"] = "elite"
            sess["saved_jobs"] = [
                {
                    "id": "saved-job-1",
                    "title": "Backend Engineer",
                    "company": "Acme",
                    "location": "Remote",
                    "job_url": "",
                    "notes": "",
                    "source": "manual",
                    "status": "Saved",
                    "created_at": "2026-04-11 10:00",
                }
            ]
        resp = client.get("/job/saved-job-1")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode()
        self.assertIn("Analyze your resume", html)
        self.assertIn("targeted application", html)


# ── M115 — Submission Confidence Layer Tests ─────────────────────


class TestM115ConfidenceLayer(unittest.TestCase):
    """Confidence checklist renders in targeted flows."""

    def test_confidence_checklist_renders_with_enhanced(self):
        app, client = _make_client()
        _seed_session(
            client,
            report_data={"profile": _PROFILE, "match": _MATCH, "tailored": _TAILORED},
            enhanced=_ENHANCED,
        )
        resp = client.get("/resume-preview")
        html = resp.data.decode()
        self.assertIn("confidence-checklist", html)
        self.assertIn("Pre-Submission Checklist", html)
        self.assertIn("checklist-pass", html)

    def test_confidence_checklist_job_targeted(self):
        app, client = _make_client()
        _seed_session(
            client,
            report_data={"profile": _PROFILE, "match": _MATCH, "tailored": _TAILORED},
            enhanced=_ENHANCED,
        )
        resp = client.get("/resume-preview")
        html = resp.data.decode()
        self.assertIn("Tailored to selected role", html)
        self.assertIn("Matched skills emphasized", html)
        self.assertIn("Missing skills not fabricated", html)
        self.assertIn("Final manual review recommended", html)


# ── Pricing/Trial Engine Tests ───────────────────────────────────


class TestTrialEngine(unittest.TestCase):
    """Trial activation, expiry, and tier integration."""

    def test_trial_tier_in_tier_order(self):
        from app.utils.tier_config import TIER_ORDER

        self.assertIn("trial", TIER_ORDER)

    def test_trial_has_full_access(self):
        from app.utils.tier_config import has_access

        features = [
            "resume_analysis",
            "enhance_resume",
            "generate_cover_letter",
            "save_package",
            "create_alert",
            "prepare_application",
        ]
        for feat in features:
            self.assertTrue(has_access("trial", feat), f"trial should access {feat}")

    def test_start_trial_sets_fields(self):
        from app.utils.tier_config import start_trial
        from app.models import UserIdentity

        user = UserIdentity(id="trial-test-1")
        start_trial(user)
        self.assertEqual(user.tier, "trial")
        self.assertIsNotNone(user.trial_start)
        self.assertIsNotNone(user.trial_end)
        delta = (user.trial_end - user.trial_start).days
        self.assertEqual(delta, 7)

    def test_trial_expiry_downgrades_to_free(self):
        from app.utils.tier_config import check_trial_expiry
        from app.models import UserIdentity

        user = UserIdentity(id="trial-test-2", tier="trial")
        user.trial_start = datetime.utcnow() - timedelta(days=8)
        user.trial_end = datetime.utcnow() - timedelta(days=1)
        result = check_trial_expiry(user)
        self.assertEqual(result, "free")
        self.assertEqual(user.tier, "free")

    def test_trial_not_expired_stays_trial(self):
        from app.utils.tier_config import check_trial_expiry
        from app.models import UserIdentity

        user = UserIdentity(id="trial-test-3", tier="trial")
        user.trial_start = datetime.utcnow()
        user.trial_end = datetime.utcnow() + timedelta(days=5)
        result = check_trial_expiry(user)
        self.assertEqual(result, "trial")

    def test_trial_days_remaining(self):
        from app.utils.tier_config import trial_days_remaining
        from app.models import UserIdentity

        user = UserIdentity(id="trial-test-4", tier="trial")
        user.trial_end = datetime.utcnow() + timedelta(days=3)
        days = trial_days_remaining(user)
        self.assertIn(days, [2, 3])  # depends on time of day

    def test_trial_days_remaining_none_for_free(self):
        from app.utils.tier_config import trial_days_remaining
        from app.models import UserIdentity

        user = UserIdentity(id="trial-test-5", tier="free")
        self.assertIsNone(trial_days_remaining(user))

    def test_can_use_job_match_trial(self):
        from app.utils.tier_config import can_use_job_match
        from app.models import UserIdentity

        user = UserIdentity(id="trial-test-6", tier="trial")
        user.trial_end = datetime.utcnow() + timedelta(days=5)
        self.assertTrue(can_use_job_match(user))

    def test_can_use_job_match_free_limit(self):
        from app.utils.tier_config import can_use_job_match, reset_daily_usage
        from app.models import UserIdentity

        user = UserIdentity(id="trial-test-7", tier="free")
        user.daily_matches_used = 5
        user.last_usage_reset = datetime.utcnow()
        self.assertFalse(can_use_job_match(user))

    def test_can_use_job_match_free_under_limit(self):
        from app.utils.tier_config import can_use_job_match
        from app.models import UserIdentity

        user = UserIdentity(id="trial-test-8", tier="free")
        user.daily_matches_used = 0
        user.last_usage_reset = datetime.utcnow()
        self.assertTrue(can_use_job_match(user))

    def test_new_user_gets_trial(self):
        """New user creation should auto-start trial."""
        app, client = _make_client()
        from app.db import db
        from app.models import UserIdentity

        with app.app_context():
            # Delete the test user so a fresh one is created
            fresh_id = "fresh-trial-test"
            existing = UserIdentity.query.filter_by(id=fresh_id).first()
            if existing:
                db.session.delete(existing)
                db.session.commit()

        # Access dashboard to trigger user creation via a new session
        with client.session_transaction() as sess:
            sess.clear()
        resp = client.get("/dashboard")
        self.assertEqual(resp.status_code, 200)
        with client.session_transaction() as sess:
            # New users should get trial tier
            self.assertEqual(sess.get("user_tier"), "trial")

    def test_dashboard_trial_banner_visible(self):
        from app.db import db
        from app.models import UserIdentity
        from app.utils.tier_config import start_trial

        app, client = _make_client(tier="trial")
        with app.app_context():
            user = UserIdentity.query.filter_by(id="test-user-s").first()
            if user:
                start_trial(user)
                db.session.commit()
        with client.session_transaction() as sess:
            sess["user_id"] = "test-user-s"
            sess["user_tier"] = "trial"
            sess["trial_days_left"] = 5
        resp = client.get("/dashboard")
        html = resp.data.decode()
        self.assertIn("trial-banner", html)
        self.assertIn("7-day free trial", html)


# ── M116 — Dashboard Stability Regression ────────────────────────


class TestM116DashboardStability(unittest.TestCase):
    """Dashboard continues to return 200 in all conditions."""

    def test_dashboard_empty_200(self):
        app, client = _make_client()
        with client.session_transaction() as sess:
            sess["user_id"] = "test-user-s"
            sess["user_tier"] = "elite"
        resp = client.get("/dashboard")
        self.assertEqual(resp.status_code, 200)

    def test_dashboard_populated_200(self):
        app, client = _make_client()
        _seed_session(client, report_data={"profile": _PROFILE, "match": _MATCH})
        resp = client.get("/dashboard")
        self.assertEqual(resp.status_code, 200)

    def test_resume_preview_empty_200(self):
        app, client = _make_client()
        with client.session_transaction() as sess:
            sess["user_id"] = "test-user-s"
            sess["user_tier"] = "elite"
        resp = client.get("/resume-preview")
        self.assertEqual(resp.status_code, 200)

    def test_resume_preview_populated_200(self):
        app, client = _make_client()
        _seed_session(
            client,
            report_data={"profile": _PROFILE, "match": _MATCH, "tailored": _TAILORED},
        )
        resp = client.get("/resume-preview")
        self.assertEqual(resp.status_code, 200)

    def test_pricing_returns_200(self):
        app, client = _make_client()
        with client.session_transaction() as sess:
            sess["user_id"] = "test-user-s"
            sess["user_tier"] = "free"
        resp = client.get("/pricing")
        self.assertEqual(resp.status_code, 200)


if __name__ == "__main__":
    unittest.main()
