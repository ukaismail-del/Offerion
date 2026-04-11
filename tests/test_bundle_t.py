"""Tests for Bundle T — Conversion + Trust + Release Hardening (M117-M122)."""

import os
import sys
import unittest

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
        existing = UserIdentity.query.filter_by(id="test-user-t").first()
        if existing:
            existing.tier = tier
            db.session.commit()
        else:
            user = UserIdentity(id="test-user-t", tier=tier)
            db.session.add(user)
            db.session.commit()

    return app, client


def _seed_session(client, report_data=None, enhanced=None, tier="elite"):
    with client.session_transaction() as sess:
        sess["user_id"] = "test-user-t"
        sess["user_tier"] = tier
        if report_data:
            sess["report_data"] = report_data
        if enhanced:
            sess["enhanced_resume"] = enhanced


# ── M117 — Conversion Clarity Tests ─────────────────────────────


class TestM117ConversionClarity(unittest.TestCase):
    """Value messaging renders across key pages."""

    def test_dashboard_hero_value_statement(self):
        app, client = _make_client()
        _seed_session(client, report_data={"profile": _PROFILE, "match": _MATCH})
        resp = client.get("/dashboard")
        html = resp.data.decode()
        self.assertIn("analyzed your resume", html)

    def test_pricing_operator_tagline(self):
        app, client = _make_client()
        with client.session_transaction() as sess:
            sess["user_id"] = "test-user-t"
            sess["user_tier"] = "free"
        resp = client.get("/pricing")
        html = resp.data.decode()
        self.assertIn("Turn your resume into targeted applications in minutes", html)

    def test_pricing_why_upgrade_copy(self):
        app, client = _make_client()
        with client.session_transaction() as sess:
            sess["user_id"] = "test-user-t"
            sess["user_tier"] = "free"
        resp = client.get("/pricing")
        html = resp.data.decode()
        self.assertIn("Why upgrade?", html)
        self.assertIn("Comet unlocks AI enhancement", html)

    def test_resume_preview_upsell_mentions_applications(self):
        app, client = _make_client(tier="free")
        _seed_session(
            client,
            report_data={"profile": _PROFILE, "match": _MATCH},
            tier="free",
        )
        resp = client.get("/resume-preview")
        html = resp.data.decode()
        self.assertIn("targeted applications", html)


# ── M118 — Upgrade Flow Tests ───────────────────────────────────


class TestM118UpgradeFlow(unittest.TestCase):
    """Gate messages are specific and redirect contextually."""

    def test_gate_message_for_enhance_resume(self):
        app, client = _make_client(tier="free")
        with client.session_transaction() as sess:
            sess["user_id"] = "test-user-t"
            sess["user_tier"] = "free"
        resp = client.get("/enhance-resume", follow_redirects=True)
        html = resp.data.decode()
        self.assertIn("AI resume enhancement", html)
        self.assertIn("Comet", html)

    def test_gate_message_for_prepare_application(self):
        app, client = _make_client(tier="free")
        with client.session_transaction() as sess:
            sess["user_id"] = "test-user-t"
            sess["user_tier"] = "free"
        resp = client.get("/prepare-application", follow_redirects=True)
        html = resp.data.decode()
        self.assertIn("One-click application prep", html)
        self.assertIn("Operator", html)

    def test_upgrade_redirects_back_to_workflow(self):
        app, client = _make_client(tier="free")
        with client.session_transaction() as sess:
            sess["user_id"] = "test-user-t"
            sess["user_tier"] = "free"
        resp = client.get("/upgrade/operator?return_to=/resume-preview")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/resume-preview", resp.headers["Location"])

    def test_pricing_gate_return_hint(self):
        app, client = _make_client(tier="free")
        with client.session_transaction() as sess:
            sess["user_id"] = "test-user-t"
            sess["user_tier"] = "free"
            sess["gate_message"] = "Test gate message"
            sess["gate_return_to"] = "/resume-preview"
        resp = client.get("/pricing")
        html = resp.data.decode()
        self.assertIn("return_to", html)
        self.assertIn("After upgrading", html)


# ── M119 — Usage Visibility Tests ────────────────────────────────


class TestM119UsageVisibility(unittest.TestCase):
    """Usage signals render in dashboard and preview."""

    def test_dashboard_shows_resume_analyzed_signal(self):
        app, client = _make_client()
        _seed_session(client, report_data={"profile": _PROFILE, "match": _MATCH})
        resp = client.get("/dashboard")
        html = resp.data.decode()
        self.assertIn("usage-signal-chip", html)
        self.assertIn("Resume analyzed", html)

    def test_dashboard_no_signals_when_empty(self):
        app, client = _make_client()
        with client.session_transaction() as sess:
            sess["user_id"] = "test-user-t"
            sess["user_tier"] = "elite"
        resp = client.get("/dashboard")
        html = resp.data.decode()
        self.assertNotIn("usage-signal-chip", html)

    def test_preview_shows_usage_signals(self):
        app, client = _make_client()
        _seed_session(
            client,
            report_data={"profile": _PROFILE, "match": _MATCH, "tailored": _TAILORED},
            enhanced=_ENHANCED,
        )
        resp = client.get("/resume-preview")
        html = resp.data.decode()
        self.assertIn("Resume analyzed", html)
        self.assertIn("Resume enhanced", html)

    def test_usage_signals_css_in_stylesheet(self):
        app, client = _make_client()
        resp = client.get("/static/styles.css")
        css = resp.data.decode()
        self.assertIn("usage-signal-chip", css)


# ── M120 — Trust Layer Tests ────────────────────────────────────


class TestM120TrustLayer(unittest.TestCase):
    """Trust messaging appears in resume preview and application prep."""

    def test_trust_messaging_in_preview_with_enhanced(self):
        app, client = _make_client()
        _seed_session(
            client,
            report_data={"profile": _PROFILE, "match": _MATCH, "tailored": _TAILORED},
            enhanced=_ENHANCED,
        )
        resp = client.get("/resume-preview")
        html = resp.data.decode()
        self.assertIn("Content is based on your resume", html)
        self.assertIn("Missing skills are not fabricated", html)
        self.assertIn("Final manual review recommended", html)

    def test_trust_layer_not_shown_without_enhanced(self):
        app, client = _make_client()
        _seed_session(
            client,
            report_data={"profile": _PROFILE, "match": _MATCH},
        )
        resp = client.get("/resume-preview")
        html = resp.data.decode()
        self.assertNotIn("trust-layer", html)

    def test_trust_css_in_stylesheet(self):
        app, client = _make_client()
        resp = client.get("/static/styles.css")
        css = resp.data.decode()
        self.assertIn("trust-layer-text", css)


# ── M121 — Release Hardening Tests ──────────────────────────────


class TestM121ReleaseHardening(unittest.TestCase):
    """Template rendering is stable across all states."""

    def test_dashboard_empty_200(self):
        app, client = _make_client()
        with client.session_transaction() as sess:
            sess["user_id"] = "test-user-t"
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
            sess["user_id"] = "test-user-t"
            sess["user_tier"] = "elite"
        resp = client.get("/resume-preview")
        self.assertEqual(resp.status_code, 200)

    def test_resume_preview_with_job_context_200(self):
        app, client = _make_client()
        report = {
            "profile": _PROFILE,
            "match": _MATCH,
            "tailored": _TAILORED,
            "job_context": {
                "title": "Backend Dev",
                "company": "Acme",
                "description": "Build APIs",
                "skills": ["python"],
            },
        }
        _seed_session(client, report_data=report, enhanced=_ENHANCED)
        resp = client.get("/resume-preview")
        self.assertEqual(resp.status_code, 200)

    def test_resume_preview_without_job_context_200(self):
        app, client = _make_client()
        _seed_session(
            client,
            report_data={"profile": _PROFILE, "match": _MATCH},
        )
        resp = client.get("/resume-preview")
        self.assertEqual(resp.status_code, 200)

    def test_pricing_returns_200_free(self):
        app, client = _make_client()
        with client.session_transaction() as sess:
            sess["user_id"] = "test-user-t"
            sess["user_tier"] = "free"
        resp = client.get("/pricing")
        self.assertEqual(resp.status_code, 200)

    def test_pricing_returns_200_trial(self):
        app, client = _make_client(tier="trial")
        with client.session_transaction() as sess:
            sess["user_id"] = "test-user-t"
            sess["user_tier"] = "trial"
            sess["trial_days_left"] = 5
        resp = client.get("/pricing")
        self.assertEqual(resp.status_code, 200)


# ── M122 — Pricing + Tier Integration Tests ─────────────────────


class TestM122PricingTiers(unittest.TestCase):
    """Pricing renders with updated tiers and Operator is highlighted."""

    def test_pricing_renders_all_tiers(self):
        app, client = _make_client()
        with client.session_transaction() as sess:
            sess["user_id"] = "test-user-t"
            sess["user_tier"] = "free"
        resp = client.get("/pricing")
        html = resp.data.decode()
        self.assertIn("Free", html)
        self.assertIn("Comet", html)
        self.assertIn("Operator", html)
        self.assertIn("Professional", html)

    def test_pricing_no_elite_displayed(self):
        app, client = _make_client()
        with client.session_transaction() as sess:
            sess["user_id"] = "test-user-t"
            sess["user_tier"] = "free"
        resp = client.get("/pricing")
        html = resp.data.decode()
        self.assertNotIn('href="/upgrade/elite"', html)

    def test_operator_is_highlighted(self):
        app, client = _make_client()
        with client.session_transaction() as sess:
            sess["user_id"] = "test-user-t"
            sess["user_tier"] = "free"
        resp = client.get("/pricing")
        html = resp.data.decode()
        self.assertIn("pricing-card-featured", html)
        self.assertIn("Most Popular", html)

    def test_updated_prices_displayed(self):
        app, client = _make_client()
        with client.session_transaction() as sess:
            sess["user_id"] = "test-user-t"
            sess["user_tier"] = "free"
        resp = client.get("/pricing")
        html = resp.data.decode()
        self.assertIn("$19/mo", html)  # Comet
        self.assertIn("$39/mo", html)  # Operator
        self.assertIn("$59/mo", html)  # Professional

    def test_no_legacy_pricing(self):
        app, client = _make_client()
        with client.session_transaction() as sess:
            sess["user_id"] = "test-user-t"
            sess["user_tier"] = "free"
        resp = client.get("/pricing")
        html = resp.data.decode()
        self.assertNotIn("$9/mo", html)
        self.assertNotIn("$29/mo", html)
        self.assertNotIn("$49/mo", html)

    def test_free_tier_limitations_enforced(self):
        from app.utils.tier_config import has_access

        self.assertTrue(has_access("free", "resume_analysis"))
        self.assertFalse(has_access("free", "enhance_resume"))
        self.assertFalse(has_access("free", "save_job"))

    def test_pricing_safe_for_trial_users(self):
        from app.db import db
        from app.models import UserIdentity
        from app.utils.tier_config import start_trial

        app, client = _make_client(tier="trial")
        with app.app_context():
            user = UserIdentity.query.filter_by(id="test-user-t").first()
            if user:
                start_trial(user)
                db.session.commit()
        with client.session_transaction() as sess:
            sess["user_id"] = "test-user-t"
            sess["user_tier"] = "trial"
            sess["trial_days_left"] = 5
        resp = client.get("/pricing")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode()
        self.assertIn("trial-banner", html)
        self.assertNotIn('href="/upgrade/trial"', html)

    def test_operator_features_listed(self):
        app, client = _make_client()
        with client.session_transaction() as sess:
            sess["user_id"] = "test-user-t"
            sess["user_tier"] = "free"
        resp = client.get("/pricing")
        html = resp.data.decode()
        self.assertIn("Full job matching engine", html)
        self.assertIn("One-click application prep", html)


if __name__ == "__main__":
    unittest.main()
