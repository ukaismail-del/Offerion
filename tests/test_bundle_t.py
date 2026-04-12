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

    app = create_app(testing=True)
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


# ── BT-01 — CSRF Protection Tests ──────────────────────────────


class TestBT01CsrfProtection(unittest.TestCase):
    """CSRF is enforced in production and disabled in tests."""

    def test_csrf_disabled_in_testing(self):
        from app import create_app

        app = create_app(testing=True)
        self.assertFalse(app.config.get("WTF_CSRF_ENABLED"))

    def test_csrf_enabled_in_production(self):
        from app import create_app

        app = create_app(testing=False)
        self.assertTrue(app.config.get("WTF_CSRF_ENABLED"))

    def test_dashboard_post_works_in_test_mode(self):
        app, client = _make_client()
        _seed_session(client)
        resp = client.post("/dashboard")
        self.assertIn(resp.status_code, (200, 302))


# ── BT-02 — UserState Persistence Tests ────────────────────────


class TestBT02UserStatePersistence(unittest.TestCase):
    """Heavy session blobs survive via UserState table."""

    def test_save_and_load_user_state(self):
        from app.utils.persistence import save_user_state, load_user_state

        app, _ = _make_client()
        with app.app_context():
            fake_session = {
                "report_data": {"profile": _PROFILE, "match": _MATCH},
                "resume_text": "Sample resume text for testing",
                "enhanced_resume": _ENHANCED,
            }
            result = save_user_state("test-user-t", fake_session)
            self.assertTrue(result)

            target = {}
            load_user_state("test-user-t", target)
            self.assertIn("report_data", target)
            self.assertEqual(target["report_data"]["match"]["score"], 72)
            self.assertEqual(target["resume_text"], "Sample resume text for testing")
            self.assertIn("enhanced_resume", target)

    def test_load_does_not_overwrite_existing(self):
        from app.utils.persistence import save_user_state, load_user_state

        app, _ = _make_client()
        with app.app_context():
            save_user_state(
                "test-user-t",
                {
                    "report_data": {"profile": _PROFILE, "match": _MATCH},
                },
            )

            target = {"report_data": {"custom": "data"}}
            load_user_state("test-user-t", target)
            self.assertEqual(target["report_data"], {"custom": "data"})

    def test_bootstrap_loads_user_state(self):
        from app.utils.persistence import save_user_state

        app, client = _make_client()
        with app.app_context():
            save_user_state(
                "test-user-t",
                {
                    "report_data": {"profile": _PROFILE, "match": _MATCH},
                    "resume_text": "Persisted resume text",
                },
            )

        with client.session_transaction() as sess:
            sess["user_id"] = "test-user-t"
            sess["user_tier"] = "elite"

        resp = client.get("/dashboard")
        self.assertEqual(resp.status_code, 200)

        with client.session_transaction() as sess:
            self.assertIn("report_data", sess)
            self.assertEqual(sess["resume_text"], "Persisted resume text")


# ── BT-03 — SharedReport Durability Tests ──────────────────────


class TestBT03SharedReportDurability(unittest.TestCase):
    """Shared reports persist in DB, survive session loss."""

    def test_save_and_load_shared_report(self):
        from app.utils.persistence import save_shared_report, load_shared_report
        import uuid

        app, _ = _make_client()
        rid = "sr" + uuid.uuid4().hex[:8]
        with app.app_context():
            snapshot = {
                "id": rid,
                "score": 85,
                "target_role": "Dev",
                "top_skills": ["python"],
                "summary": "Good match",
                "strengths": [],
                "created_at": "2025-01-01 00:00:00",
            }
            rec = save_shared_report(rid, snapshot, user_id="test-user-t")
            self.assertIsNotNone(rec)

            loaded = load_shared_report(rid)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded["score"], 85)
            self.assertEqual(loaded["target_role"], "Dev")

    def test_share_report_route_loads_from_db(self):
        from app.utils.persistence import save_shared_report
        import uuid

        app, client = _make_client()
        rid = "db" + uuid.uuid4().hex[:8]
        with app.app_context():
            snapshot = {
                "id": rid,
                "score": 90,
                "target_role": "Engineer",
                "top_skills": ["java"],
                "summary": "Strong match",
                "strengths": ["API design"],
                "created_at": "2025-01-01 00:00:00",
            }
            save_shared_report(rid, snapshot)

        resp = client.get(f"/share/report/{rid}")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode()
        self.assertIn("90", html)

    def test_share_report_missing_returns_404(self):
        _, client = _make_client()
        resp = client.get("/share/report/nonexistent99")
        self.assertEqual(resp.status_code, 404)


# ── BT-04 — Stripe Foundation Tests ────────────────────────────


class TestBT04StripeFoundation(unittest.TestCase):
    """Stripe utility and route scaffolding."""

    def test_stripe_config_no_key(self):
        from app.utils.stripe_billing import get_stripe_config

        conf = get_stripe_config()
        self.assertIn("has_secret_key", conf)
        self.assertIn("prices", conf)

    def test_checkout_route_redirects_without_stripe(self):
        app, client = _make_client()
        _seed_session(client)
        resp = client.post("/checkout/operator")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("upgrade", resp.headers["Location"].lower())

    def test_webhook_rejects_without_config(self):
        app, client = _make_client()
        resp = client.post(
            "/stripe/webhook",
            data=b"{}",
            headers={"Stripe-Signature": "fake"},
        )
        self.assertEqual(resp.status_code, 400)

    def test_checkout_success_redirects_to_pricing(self):
        app, client = _make_client()
        _seed_session(client)
        resp = client.get("/checkout/success")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("pricing", resp.headers["Location"].lower())

    def test_stripe_webhook_is_csrf_exempt(self):
        from app import create_app

        app = create_app(testing=False)
        app.config["SECRET_KEY"] = "test"
        client = app.test_client()
        resp = client.post(
            "/stripe/webhook",
            data=b"{}",
            headers={"Stripe-Signature": "test"},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertNotIn(b"CSRF", resp.data)

    def test_stripe_fields_on_user_model(self):
        app, _ = _make_client()
        with app.app_context():
            from app.models import UserIdentity

            user = UserIdentity.query.get("test-user-t")
            self.assertTrue(hasattr(user, "stripe_customer_id"))
            self.assertTrue(hasattr(user, "stripe_subscription_id"))


# ── BT-05 — Model Existence Tests ──────────────────────────────


class TestBT05ModelExistence(unittest.TestCase):
    """New models are importable and tables are created."""

    def test_user_state_model_exists(self):
        from app.models import UserState

        self.assertEqual(UserState.__tablename__, "user_state")

    def test_shared_report_model_exists(self):
        from app.models import SharedReport

        self.assertEqual(SharedReport.__tablename__, "shared_report")

    def test_user_state_table_created(self):
        app, _ = _make_client()
        with app.app_context():
            from app.db import db

            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            self.assertIn("user_state", tables)
            self.assertIn("shared_report", tables)


if __name__ == "__main__":
    unittest.main()
