"""Tests for Bundle R — Application Continuity + UX Polish Hardening (M105-M110)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Shared fixtures ──────────────────────────────────────────────

_PROFILE = {"skills": ["python", "sql", "flask"], "name": "Test User"}
_MATCH = {"target_role": "Backend Developer"}
_JOB_CONTEXT = {
    "job_id": "r-test-1",
    "title": "Senior Python Engineer",
    "company": "Acme Corp",
    "location": "Remote",
    "description": "Build REST APIs with Flask and Docker.",
    "skills": ["python", "flask", "docker"],
}
_JOB_CONTEXT_FULL = {
    "job_id": "r-test-2",
    "title": "Senior Python Engineer",
    "company": "Acme Corp",
    "location": "Remote",
    "description": "Build REST APIs with Flask and Docker.",
    "skills": ["python", "flask", "docker"],
    "matched_skills": ["python", "flask"],
    "intelligence": {
        "keywords": ["python", "flask", "docker"],
        "seniority_hint": "Senior",
        "domain_hint": "Backend",
        "required_skills": ["python", "flask"],
        "preferred_skills": ["docker"],
        "responsibility_signals": ["build rest apis"],
    },
    "gap": {
        "fit_score": 0.75,
        "fit_level": "Moderate",
        "matched_skills": ["python", "flask"],
        "missing_skills": ["docker"],
        "resume_strengths": ["Strong alignment in: python, flask"],
        "resume_gaps": ["Missing required skills: docker"],
        "recommended_focus": ["Highlight proficiency in python"],
    },
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

    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    client = app.test_client()

    with app.app_context():
        if not UserIdentity.query.filter_by(id="test-user").first():
            user = UserIdentity(id="test-user", tier="elite")
            db.session.add(user)
            db.session.commit()

    return app, client


def _make_package(report_data=None, intel=None, gap=None):
    """Create a package via save_package for testing."""
    from app.utils.application_package import save_package

    session_data = {
        "report_data": report_data or {"profile": _PROFILE, "match": _MATCH},
    }
    if intel is not None:
        session_data["selected_job_intelligence"] = intel
    if gap is not None:
        session_data["selected_job_gap"] = gap
    return save_package(session_data)


# ── M105 — Saved Package Reopen Reliability ──────────────────────


class TestPackageReopenReliability(unittest.TestCase):
    """M105 — open_application_package handles stale/partial/corrupt data."""

    def setUp(self):
        self.app, self.client = _make_client()

    def test_reopen_with_full_intel_gap_restores(self):
        """Package with embedded intel/gap restores both to session."""
        rd = {"profile": _PROFILE, "match": _MATCH, "job_context": _JOB_CONTEXT}
        pkg = _make_package(report_data=rd, intel=_INTEL, gap=_GAP)

        with self.client.session_transaction() as s:
            s["user_id"] = "test-user"
            s["user_tier"] = "elite"
            s["application_packages"] = [pkg]
            s["tier_usage"] = {}

        resp = self.client.get(
            f"/application-package/{pkg['id']}", follow_redirects=False
        )
        self.assertIn(resp.status_code, [302, 303])

        with self.client.session_transaction() as s:
            self.assertIsNotNone(s.get("selected_job_intelligence"))
            self.assertIsNotNone(s.get("selected_job_gap"))
            self.assertEqual(
                s["selected_job_intelligence"]["domain_hint"], "Backend"
            )

    def test_reopen_missing_gap_regenerates(self):
        """Package with intel but no gap triggers regeneration."""
        rd = {"profile": _PROFILE, "match": _MATCH, "job_context": _JOB_CONTEXT}
        pkg = _make_package(report_data=rd, intel=_INTEL, gap=None)

        with self.client.session_transaction() as s:
            s["user_id"] = "test-user"
            s["user_tier"] = "elite"
            s["application_packages"] = [pkg]
            s["tier_usage"] = {}

        resp = self.client.get(
            f"/application-package/{pkg['id']}", follow_redirects=False
        )
        self.assertIn(resp.status_code, [302, 303])

        with self.client.session_transaction() as s:
            # intel should be restored from package
            self.assertIsNotNone(s.get("selected_job_intelligence"))
            # gap should have been regenerated
            self.assertIsNotNone(s.get("selected_job_gap"))

    def test_reopen_no_job_context_clears_intel_gap(self):
        """Package with no job_context clears any prior intel/gap."""
        rd = {"profile": _PROFILE, "match": _MATCH}  # no job_context
        pkg = _make_package(report_data=rd)

        with self.client.session_transaction() as s:
            s["user_id"] = "test-user"
            s["user_tier"] = "elite"
            s["application_packages"] = [pkg]
            # Pre-seed intel/gap that should be cleared
            s["selected_job_intelligence"] = _INTEL
            s["selected_job_gap"] = _GAP
            s["tier_usage"] = {}

        resp = self.client.get(
            f"/application-package/{pkg['id']}", follow_redirects=False
        )
        self.assertIn(resp.status_code, [302, 303])

        with self.client.session_transaction() as s:
            self.assertIsNone(s.get("selected_job_intelligence"))
            self.assertIsNone(s.get("selected_job_gap"))

    def test_reopen_missing_package_redirects(self):
        """Opening a non-existent package redirects to dashboard."""
        with self.client.session_transaction() as s:
            s["user_id"] = "test-user"
            s["user_tier"] = "elite"
            s["application_packages"] = []
            s["tier_usage"] = {}

        resp = self.client.get(
            "/application-package/nonexistent123", follow_redirects=False
        )
        self.assertIn(resp.status_code, [302, 303])

    def test_reopen_empty_report_data_no_crash(self):
        """Package whose report_data is empty still loads without crash."""
        from app.utils.application_package import save_package

        # Manually build a package with empty report_data
        pkg = {
            "id": "empty-rd-test",
            "label": "Test",
            "target_title": "",
            "company": "",
            "created_at": "2025-01-01",
            "report_data": {},
            "enhanced_resume": None,
            "cover_letter_draft": None,
            "enhanced_cover_letter": None,
            "selected_job_intelligence": None,
            "selected_job_gap": None,
        }

        with self.client.session_transaction() as s:
            s["user_id"] = "test-user"
            s["user_tier"] = "elite"
            s["application_packages"] = [pkg]
            s["tier_usage"] = {}

        resp = self.client.get(
            "/application-package/empty-rd-test", follow_redirects=False
        )
        # Should redirect (302/303) not crash (500)
        self.assertIn(resp.status_code, [302, 303])


# ── M106 — Application Draft Continuity ──────────────────────────


class TestDraftContinuity(unittest.TestCase):
    """M106 — Cover letter routes pass job_context through."""

    def setUp(self):
        self.app, self.client = _make_client()

    def test_generate_cover_letter_with_job_context(self):
        """Generate CL route flows job_context to build_cover_letter."""
        with self.client.session_transaction() as s:
            s["user_id"] = "test-user"
            s["user_tier"] = "elite"
            s["report_data"] = {
                "profile": _PROFILE,
                "match": _MATCH,
                "job_context": _JOB_CONTEXT,
            }
            s["tier_usage"] = {}

        resp = self.client.get("/generate-cover-letter", follow_redirects=False)
        self.assertIn(resp.status_code, [302, 303])

        with self.client.session_transaction() as s:
            draft = s.get("cover_letter_draft")
            self.assertIsNotNone(draft)
            # Draft should exist — full content tested elsewhere

    def test_enhance_cover_letter_with_job_context(self):
        """Enhance CL route reads job_context and passes it through."""
        from app.utils.cover_letter_builder import build_cover_letter

        draft = build_cover_letter(profile=_PROFILE, match=_MATCH)

        with self.client.session_transaction() as s:
            s["user_id"] = "test-user"
            s["user_tier"] = "elite"
            s["report_data"] = {
                "profile": _PROFILE,
                "match": _MATCH,
                "job_context": _JOB_CONTEXT,
            }
            s["cover_letter_draft"] = draft
            s["tier_usage"] = {}

        resp = self.client.get("/enhance-cover-letter", follow_redirects=False)
        self.assertIn(resp.status_code, [302, 303])

        with self.client.session_transaction() as s:
            ecl = s.get("enhanced_cover_letter")
            self.assertIsNotNone(ecl)
            self.assertIn("full_text", ecl)

    def test_enhance_cover_letter_without_job_context(self):
        """Enhance CL route works when no job_context exists."""
        from app.utils.cover_letter_builder import build_cover_letter

        draft = build_cover_letter(profile=_PROFILE, match=_MATCH)

        with self.client.session_transaction() as s:
            s["user_id"] = "test-user"
            s["user_tier"] = "elite"
            s["report_data"] = {"profile": _PROFILE, "match": _MATCH}
            s["cover_letter_draft"] = draft
            s["tier_usage"] = {}

        resp = self.client.get("/enhance-cover-letter", follow_redirects=False)
        self.assertIn(resp.status_code, [302, 303])

        with self.client.session_transaction() as s:
            ecl = s.get("enhanced_cover_letter")
            self.assertIsNotNone(ecl)


# ── M107 — Resume/Cover Letter UX Clarity ────────────────────────


class TestTargetingMetadata(unittest.TestCase):
    """M107 — enhance_resume returns targeting dict; enhance_cover_letter returns targeting_mode."""

    def test_enhance_resume_targeted_mode(self):
        """With job_context, targeting.mode == 'job-targeted'."""
        from app.utils.resume_enhancer import enhance_resume

        result = enhance_resume(
            profile=_PROFILE, match=_MATCH, job_context=_JOB_CONTEXT_FULL
        )
        self.assertIsNotNone(result)
        self.assertIn("targeting", result)
        self.assertEqual(result["targeting"]["mode"], "job-targeted")
        self.assertEqual(result["targeting"]["job_title"], "Senior Python Engineer")
        self.assertEqual(result["targeting"]["company"], "Acme Corp")

    def test_enhance_resume_generic_mode(self):
        """Without job_context, targeting.mode == 'generic'."""
        from app.utils.resume_enhancer import enhance_resume

        result = enhance_resume(profile=_PROFILE, match=_MATCH)
        self.assertIsNotNone(result)
        self.assertEqual(result["targeting"]["mode"], "generic")
        self.assertIsNone(result["targeting"]["job_title"])

    def test_enhance_cover_letter_targeted_mode(self):
        """With job_context, targeting_mode == 'job-targeted'."""
        from app.utils.cover_letter_builder import build_cover_letter
        from app.utils.cover_letter_enhancer import enhance_cover_letter

        draft = build_cover_letter(profile=_PROFILE, match=_MATCH)
        result = enhance_cover_letter(draft, job_context=_JOB_CONTEXT)
        self.assertIsNotNone(result)
        self.assertEqual(result["targeting_mode"], "job-targeted")

    def test_enhance_cover_letter_generic_mode(self):
        """Without job_context, targeting_mode == 'generic'."""
        from app.utils.cover_letter_builder import build_cover_letter
        from app.utils.cover_letter_enhancer import enhance_cover_letter

        draft = build_cover_letter(profile=_PROFILE, match=_MATCH)
        result = enhance_cover_letter(draft)
        self.assertIsNotNone(result)
        self.assertEqual(result["targeting_mode"], "generic")


# ── M108 — Targeting Explainability ──────────────────────────────


class TestTargetingExplainability(unittest.TestCase):
    """M108 — _build_targeting_metadata populates matched/omitted/emphasized."""

    def test_matched_skills_populated(self):
        from app.utils.resume_enhancer import enhance_resume

        result = enhance_resume(
            profile=_PROFILE, match=_MATCH, job_context=_JOB_CONTEXT_FULL
        )
        targeting = result["targeting"]
        self.assertIn("python", targeting["matched"])
        self.assertIn("flask", targeting["matched"])

    def test_omitted_skills_not_inserted(self):
        """Skills the user doesn't have should appear in omitted, not enhanced_skills."""
        from app.utils.resume_enhancer import enhance_resume

        result = enhance_resume(
            profile=_PROFILE, match=_MATCH, job_context=_JOB_CONTEXT_FULL
        )
        targeting = result["targeting"]
        # docker is missing from profile but required by job
        # If it was NOT inserted into enhanced_skills, it should be in omitted
        enhanced_lower = {s.lower() for s in result["enhanced_skills"]}
        for skill in targeting["omitted"]:
            self.assertNotIn(
                skill.lower(),
                enhanced_lower,
                f"Omitted skill '{skill}' should not be in enhanced_skills",
            )

    def test_emphasized_focus_areas(self):
        from app.utils.resume_enhancer import enhance_resume

        result = enhance_resume(
            profile=_PROFILE, match=_MATCH, job_context=_JOB_CONTEXT_FULL
        )
        targeting = result["targeting"]
        # emphasized should come from gap.recommended_focus
        self.assertIsInstance(targeting["emphasized"], list)

    def test_generic_has_empty_lists(self):
        from app.utils.resume_enhancer import enhance_resume

        result = enhance_resume(profile=_PROFILE, match=_MATCH)
        targeting = result["targeting"]
        self.assertEqual(targeting["matched"], [])
        self.assertEqual(targeting["omitted"], [])
        self.assertEqual(targeting["emphasized"], [])


# ── M109 — Template Rendering Safety ─────────────────────────────


class TestTemplateRenderingSafety(unittest.TestCase):
    """M109 — Templates render without error in various states."""

    def setUp(self):
        self.app, self.client = _make_client()

    def test_resume_preview_with_targeting(self):
        """Preview renders when enhanced resume has targeting metadata."""
        from app.utils.resume_enhancer import enhance_resume

        enhanced = enhance_resume(
            profile=_PROFILE, match=_MATCH, job_context=_JOB_CONTEXT_FULL
        )

        with self.client.session_transaction() as s:
            s["user_id"] = "test-user"
            s["user_tier"] = "elite"
            s["report_data"] = {
                "profile": _PROFILE,
                "match": _MATCH,
                "job_context": _JOB_CONTEXT,
            }
            s["enhanced_resume"] = enhanced
            s["tier_usage"] = {}

        resp = self.client.get("/resume-preview")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode()
        self.assertIn("Targeted for:", html)

    def test_resume_preview_generic_targeting(self):
        """Preview renders generic targeting when no job_context."""
        from app.utils.resume_enhancer import enhance_resume

        enhanced = enhance_resume(profile=_PROFILE, match=_MATCH)

        with self.client.session_transaction() as s:
            s["user_id"] = "test-user"
            s["user_tier"] = "elite"
            s["report_data"] = {"profile": _PROFILE, "match": _MATCH}
            s["enhanced_resume"] = enhanced
            s["tier_usage"] = {}

        resp = self.client.get("/resume-preview")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode()
        self.assertIn("Generic Enhancement", html)

    def test_resume_preview_no_enhanced(self):
        """Preview renders when enhanced_resume is None."""
        with self.client.session_transaction() as s:
            s["user_id"] = "test-user"
            s["user_tier"] = "elite"
            s["report_data"] = {"profile": _PROFILE, "match": _MATCH}
            s["tier_usage"] = {}

        resp = self.client.get("/resume-preview")
        self.assertEqual(resp.status_code, 200)

    def test_resume_preview_with_cover_letter_targeting_mode(self):
        """Preview renders cover letter targeting_mode label."""
        from app.utils.resume_enhancer import enhance_resume
        from app.utils.cover_letter_builder import build_cover_letter
        from app.utils.cover_letter_enhancer import enhance_cover_letter

        enhanced = enhance_resume(
            profile=_PROFILE, match=_MATCH, job_context=_JOB_CONTEXT_FULL
        )
        draft = build_cover_letter(profile=_PROFILE, match=_MATCH)
        ecl = enhance_cover_letter(draft, job_context=_JOB_CONTEXT)

        with self.client.session_transaction() as s:
            s["user_id"] = "test-user"
            s["user_tier"] = "elite"
            s["report_data"] = {
                "profile": _PROFILE,
                "match": _MATCH,
                "job_context": _JOB_CONTEXT,
            }
            s["enhanced_resume"] = enhanced
            s["cover_letter_draft"] = draft
            s["enhanced_cover_letter"] = ecl
            s["tier_usage"] = {}

        resp = self.client.get("/resume-preview")
        self.assertEqual(resp.status_code, 200)

    def test_dashboard_after_package_reopen(self):
        """Dashboard renders 200 after reopening a package."""
        rd = {"profile": _PROFILE, "match": _MATCH, "job_context": _JOB_CONTEXT}
        pkg = _make_package(report_data=rd, intel=_INTEL, gap=_GAP)

        with self.client.session_transaction() as s:
            s["user_id"] = "test-user"
            s["user_tier"] = "elite"
            s["application_packages"] = [pkg]
            s["tier_usage"] = {}

        # Open package first
        self.client.get(
            f"/application-package/{pkg['id']}", follow_redirects=True
        )

        # Then go to dashboard
        resp = self.client.get("/dashboard")
        self.assertEqual(resp.status_code, 200)

    def test_dashboard_empty_state(self):
        """Dashboard still 200 in empty state (no regression from Bundle Q)."""
        resp = self.client.get("/dashboard")
        self.assertEqual(resp.status_code, 200)

    def test_dashboard_report_only(self):
        """Dashboard 200 with report_data but no selected job."""
        with self.client.session_transaction() as s:
            s["user_id"] = "test-user"
            s["user_tier"] = "elite"
            s["report_data"] = {"profile": _PROFILE, "match": _MATCH}
            s["tier_usage"] = {}
        resp = self.client.get("/dashboard")
        self.assertEqual(resp.status_code, 200)

    def test_dashboard_full_state(self):
        """Dashboard 200 with full selected job state."""
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


if __name__ == "__main__":
    unittest.main()
