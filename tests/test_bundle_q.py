"""Tests for Bundle Q — Dashboard Regression Fix + Application Depth Hardening (M99-M104)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Shared fixtures ──────────────────────────────────────────────

_PROFILE = {"skills": ["python", "sql", "flask"], "name": "Test User"}
_MATCH = {"target_role": "Backend Developer"}
_JOB_CONTEXT = {
    "job_id": "q-test-1",
    "title": "Senior Python Engineer",
    "company": "Acme Corp",
    "location": "Remote",
    "description": "Build REST APIs with Flask and Docker.",
    "skills": ["python", "flask", "docker"],
}
_INTEL = {
    "keywords": ["python", "flask", "docker"],
    "seniority_hint": "Senior",
    "domain_hint": "Backend",
    "required_skills": ["python", "flask"],
    "preferred_skills": ["docker"],
    "responsibility_signals": ["build rest apis"],
}
_GAP = {
    "fit_score": 0.75,
    "fit_level": "Moderate",
    "matched_skills": ["python", "flask"],
    "missing_skills": ["docker"],
    "resume_strengths": ["Strong alignment in: python, flask"],
    "resume_gaps": ["Missing required skills: docker"],
    "recommended_focus": ["Highlight proficiency in python"],
}


def _make_client():
    from app import create_app
    from app.db import db
    from app.models import UserIdentity

    app = create_app(testing=True)
    app.config["SECRET_KEY"] = "test-secret"
    client = app.test_client()

    with app.app_context():
        if not UserIdentity.query.filter_by(id="test-user").first():
            user = UserIdentity(id="test-user", tier="elite")
            db.session.add(user)
            db.session.commit()

    return app, client


# ── M99 — _selected_job_state Hardening ──────────────────────────


class TestSelectedJobState(unittest.TestCase):
    """M99 — _selected_job_state returns safe defaults and regenerates."""

    def setUp(self):
        self.app, self.client = _make_client()

    def test_empty_session_returns_none_triplet(self):
        """No report_data → (None, None, None)."""
        with self.client.session_transaction() as s:
            s["user_id"] = "test-user"
            s["user_tier"] = "elite"
            s["tier_usage"] = {}

        resp = self.client.get("/dashboard")
        self.assertEqual(resp.status_code, 200)

        with self.client.session_transaction() as s:
            self.assertIsNone(s.get("selected_job_intelligence"))
            self.assertIsNone(s.get("selected_job_gap"))

    def test_context_triggers_regeneration(self):
        """If job_context exists but intel/gap are missing, they regenerate."""
        with self.client.session_transaction() as s:
            s["user_id"] = "test-user"
            s["user_tier"] = "elite"
            s["report_data"] = {
                "profile": _PROFILE,
                "match": _MATCH,
                "job_context": _JOB_CONTEXT,
            }
            s["tier_usage"] = {}
            # Deliberately do NOT set selected_job_intelligence / gap

        resp = self.client.get("/dashboard")
        self.assertEqual(resp.status_code, 200)

        with self.client.session_transaction() as s:
            self.assertIsNotNone(s.get("selected_job_intelligence"))
            self.assertIsNotNone(s.get("selected_job_gap"))

    def test_existing_intel_gap_preserved(self):
        """Pre-set intel/gap must not be overwritten."""
        with self.client.session_transaction() as s:
            s["user_id"] = "test-user"
            s["user_tier"] = "elite"
            s["report_data"] = {
                "profile": _PROFILE,
                "match": _MATCH,
                "job_context": _JOB_CONTEXT,
            }
            s["selected_job_intelligence"] = _INTEL
            s["selected_job_gap"] = _GAP
            s["tier_usage"] = {}

        resp = self.client.get("/dashboard")
        self.assertEqual(resp.status_code, 200)

        with self.client.session_transaction() as s:
            self.assertEqual(s["selected_job_intelligence"]["seniority_hint"], "Senior")
            self.assertAlmostEqual(s["selected_job_gap"]["fit_score"], 0.75)


# ── M99 — Dashboard Returns 200 in All States ───────────────────


class TestDashboard200(unittest.TestCase):
    """Dashboard must return 200 regardless of session shape."""

    def setUp(self):
        self.app, self.client = _make_client()

    def test_empty_session(self):
        resp = self.client.get("/dashboard")
        # Auth now required — unauthenticated users redirect to /login
        self.assertIn(resp.status_code, [302, 303])

    def test_user_only(self):
        with self.client.session_transaction() as s:
            s["user_id"] = "test-user"
            s["user_tier"] = "elite"
            s["tier_usage"] = {}
        resp = self.client.get("/dashboard")
        self.assertEqual(resp.status_code, 200)

    def test_report_data_no_job(self):
        with self.client.session_transaction() as s:
            s["user_id"] = "test-user"
            s["user_tier"] = "elite"
            s["report_data"] = {"profile": _PROFILE, "match": _MATCH}
            s["tier_usage"] = {}
        resp = self.client.get("/dashboard")
        self.assertEqual(resp.status_code, 200)

    def test_full_selected_job(self):
        with self.client.session_transaction() as s:
            s["user_id"] = "test-user"
            s["user_tier"] = "elite"
            s["report_data"] = {
                "profile": _PROFILE,
                "match": _MATCH,
                "job_context": _JOB_CONTEXT,
            }
            s["selected_job_intelligence"] = _INTEL
            s["selected_job_gap"] = _GAP
            s["tier_usage"] = {}
        resp = self.client.get("/dashboard")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode()
        self.assertIn("Job Fit Analysis", html)

    def test_partial_selected_job_no_gap(self):
        with self.client.session_transaction() as s:
            s["user_id"] = "test-user"
            s["user_tier"] = "elite"
            s["report_data"] = {
                "profile": _PROFILE,
                "match": _MATCH,
                "job_context": _JOB_CONTEXT,
            }
            s["selected_job_intelligence"] = _INTEL
            # gap deliberately missing → should auto-regenerate
            s["tier_usage"] = {}
        resp = self.client.get("/dashboard")
        self.assertEqual(resp.status_code, 200)


# ── M99 — Resume Preview Returns 200 ────────────────────────────


class TestResumePreview200(unittest.TestCase):
    """Resume preview must not crash when selected-job data is absent."""

    def setUp(self):
        self.app, self.client = _make_client()

    def test_preview_without_selected_job(self):
        with self.client.session_transaction() as s:
            s["user_id"] = "test-user"
            s["user_tier"] = "elite"
            s["report_data"] = {"profile": _PROFILE, "match": _MATCH}
            s["tier_usage"] = {}
        resp = self.client.get("/resume-preview")
        self.assertEqual(resp.status_code, 200)

    def test_preview_with_selected_job(self):
        with self.client.session_transaction() as s:
            s["user_id"] = "test-user"
            s["user_tier"] = "elite"
            s["report_data"] = {
                "profile": _PROFILE,
                "match": _MATCH,
                "job_context": _JOB_CONTEXT,
            }
            s["selected_job_intelligence"] = _INTEL
            s["selected_job_gap"] = _GAP
            s["tier_usage"] = {}
        resp = self.client.get("/resume-preview")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode()
        self.assertIn("Targeting:", html)


# ── M100 — Package Persistence ───────────────────────────────────


class TestPackagePersistence(unittest.TestCase):
    """M100 — save_package embeds intel/gap, open_application_package restores them."""

    def test_save_includes_intel_and_gap(self):
        from app.utils.application_package import save_package

        session_data = {
            "report_data": {"profile": _PROFILE, "match": _MATCH},
            "selected_job_intelligence": _INTEL,
            "selected_job_gap": _GAP,
        }
        pkg = save_package(session_data)
        self.assertIsNotNone(pkg)
        self.assertEqual(pkg["selected_job_intelligence"]["domain_hint"], "Backend")
        self.assertAlmostEqual(pkg["selected_job_gap"]["fit_score"], 0.75)

    def test_save_without_intel_gap_still_works(self):
        from app.utils.application_package import save_package

        session_data = {"report_data": {"profile": _PROFILE, "match": _MATCH}}
        pkg = save_package(session_data)
        self.assertIsNotNone(pkg)
        self.assertIsNone(pkg["selected_job_intelligence"])
        self.assertIsNone(pkg["selected_job_gap"])

    def test_open_package_rehydrates_intel(self):
        """Opening a package that has embedded intel/gap restores them to session."""
        app, client = _make_client()

        from app.utils.application_package import save_package

        session_data = {
            "report_data": {
                "profile": _PROFILE,
                "match": _MATCH,
                "job_context": _JOB_CONTEXT,
            },
            "selected_job_intelligence": _INTEL,
            "selected_job_gap": _GAP,
        }
        pkg = save_package(session_data)

        with client.session_transaction() as s:
            s["user_id"] = "test-user"
            s["user_tier"] = "elite"
            s["application_packages"] = [pkg]
            s["tier_usage"] = {}

        resp = client.get(f"/application-package/{pkg['id']}", follow_redirects=False)
        self.assertIn(resp.status_code, [302, 303])

        with client.session_transaction() as s:
            self.assertIsNotNone(s.get("selected_job_intelligence"))
            self.assertIsNotNone(s.get("selected_job_gap"))


# ── M101 — Stronger Resume Targeting ────────────────────────────


class TestResumeTargeting(unittest.TestCase):
    """M101 — enhance_resume with job_context produces targeted output."""

    def test_enhance_with_job_context(self):
        from app.utils.resume_enhancer import enhance_resume

        result = enhance_resume(
            profile=_PROFILE,
            match=_MATCH,
            job_context=_JOB_CONTEXT,
        )
        self.assertIsNotNone(result)
        self.assertIn("enhanced_summary", result)
        self.assertIn("enhanced_skills", result)

    def test_enhance_without_job_context_still_works(self):
        from app.utils.resume_enhancer import enhance_resume

        result = enhance_resume(profile=_PROFILE, match=_MATCH)
        self.assertIsNotNone(result)


# ── M102 — Stronger Cover Letter Targeting ──────────────────────


class TestCoverLetterTargeting(unittest.TestCase):
    """M102 — enhance_cover_letter with job_context produces targeted output."""

    def test_enhance_with_job_context(self):
        from app.utils.cover_letter_builder import build_cover_letter
        from app.utils.cover_letter_enhancer import enhance_cover_letter

        draft = build_cover_letter(profile=_PROFILE, match=_MATCH)
        result = enhance_cover_letter(
            cover_letter_draft=draft,
            job_context=_JOB_CONTEXT,
        )
        self.assertIsNotNone(result)
        self.assertIn("full_text", result)

    def test_enhance_without_job_context_backward_compat(self):
        from app.utils.cover_letter_builder import build_cover_letter
        from app.utils.cover_letter_enhancer import enhance_cover_letter

        draft = build_cover_letter(profile=_PROFILE, match=_MATCH)
        result = enhance_cover_letter(cover_letter_draft=draft)
        self.assertIsNotNone(result)
        self.assertIn("full_text", result)


# ── M103 — Fit Panel UI ─────────────────────────────────────────


class TestFitPanelEmpty(unittest.TestCase):
    """M103 — Fit panel handles missing skill lists gracefully."""

    def setUp(self):
        self.app, self.client = _make_client()

    def test_empty_matched_skills_shows_hint(self):
        gap_empty_match = dict(_GAP, matched_skills=[], missing_skills=["docker"])
        with self.client.session_transaction() as s:
            s["user_id"] = "test-user"
            s["user_tier"] = "elite"
            s["report_data"] = {
                "profile": _PROFILE,
                "match": _MATCH,
                "job_context": _JOB_CONTEXT,
            }
            s["selected_job_intelligence"] = _INTEL
            s["selected_job_gap"] = gap_empty_match
            s["tier_usage"] = {}

        resp = self.client.get("/dashboard")
        self.assertEqual(resp.status_code, 200)

    def test_empty_missing_skills_shows_hint(self):
        gap_no_missing = dict(
            _GAP, matched_skills=["python"], missing_skills=[], resume_gaps=[]
        )
        with self.client.session_transaction() as s:
            s["user_id"] = "test-user"
            s["user_tier"] = "elite"
            s["report_data"] = {
                "profile": _PROFILE,
                "match": _MATCH,
                "job_context": _JOB_CONTEXT,
            }
            s["selected_job_intelligence"] = _INTEL
            s["selected_job_gap"] = gap_no_missing
            s["tier_usage"] = {}

        resp = self.client.get("/dashboard")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode()
        self.assertIn("great fit", html.lower())


if __name__ == "__main__":
    unittest.main()
