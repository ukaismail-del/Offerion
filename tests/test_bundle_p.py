"""Tests for Bundle P — Application Intelligence + Auto-Targeting (M93-M98)."""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── M93 — Job Intelligence Extractor ────────────────────────────


class TestJobIntelligence(unittest.TestCase):
    """M93 — extract_job_intelligence."""

    def test_extracts_keywords_from_title_and_description(self):
        from app.utils.job_intelligence import extract_job_intelligence

        job = {
            "title": "Senior Python Developer",
            "description": "Build REST APIs with Flask and Docker. SQL experience required.",
            "skills": ["python", "flask"],
        }
        intel = extract_job_intelligence(job)
        self.assertIn("python", intel["keywords"])
        self.assertIn("flask", intel["keywords"])
        self.assertIn("docker", intel["keywords"])
        self.assertIn("sql", intel["keywords"])

    def test_detects_seniority(self):
        from app.utils.job_intelligence import extract_job_intelligence

        job = {"title": "Senior Backend Engineer", "description": "Lead team."}
        intel = extract_job_intelligence(job)
        self.assertEqual(intel["seniority_hint"], "Senior")

    def test_detects_domain(self):
        from app.utils.job_intelligence import extract_job_intelligence

        job = {"title": "Backend Developer", "description": "Build backend services."}
        intel = extract_job_intelligence(job)
        self.assertEqual(intel["domain_hint"], "Backend")

    def test_detects_responsibilities(self):
        from app.utils.job_intelligence import extract_job_intelligence

        job = {
            "title": "Engineer",
            "description": "Design and implement scalable systems. Collaborate with cross-functional teams.",
        }
        intel = extract_job_intelligence(job)
        self.assertIn("design and implement", intel["responsibility_signals"])
        self.assertIn("cross-functional", intel["responsibility_signals"])

    def test_output_shape(self):
        from app.utils.job_intelligence import extract_job_intelligence

        job = {"title": "Analyst", "description": "Analyze data."}
        intel = extract_job_intelligence(job)
        for key in [
            "keywords",
            "required_skills",
            "preferred_skills",
            "seniority_hint",
            "domain_hint",
            "responsibility_signals",
        ]:
            self.assertIn(key, intel)

    def test_empty_job(self):
        from app.utils.job_intelligence import extract_job_intelligence

        intel = extract_job_intelligence({})
        self.assertEqual(intel["keywords"], [])
        self.assertIsNone(intel["seniority_hint"])

    def test_classifies_required_vs_preferred(self):
        from app.utils.job_intelligence import extract_job_intelligence

        job = {
            "title": "Developer",
            "description": (
                "Requirements: Must have strong experience in Python and SQL. "
                "You will build backend services and maintain databases. "
                "The ideal candidate has proven experience with these technologies. "
                "Nice to have: Familiarity with Docker and Kubernetes for deployment."
            ),
            "skills": ["python", "sql"],
        }
        intel = extract_job_intelligence(job)
        self.assertIn("python", intel["required_skills"])
        self.assertIn("sql", intel["required_skills"])
        # Docker mentioned near 'nice to have' should be preferred
        self.assertIn("docker", intel["preferred_skills"])


# ── M94 — Gap Analyzer ──────────────────────────────────────────


class TestJobGapAnalyzer(unittest.TestCase):
    """M94 — analyze_job_gap."""

    def test_identifies_matched_and_missing(self):
        from app.utils.job_gap_analyzer import analyze_job_gap

        report_data = {
            "profile": {"skills": ["python", "sql", "flask"]},
            "match": {"target_role": "Backend Developer"},
        }
        job = {
            "title": "Backend Developer",
            "skills": ["python", "sql", "docker", "kubernetes"],
            "description": "Deploy containerized services.",
        }
        result = analyze_job_gap(report_data, job)
        self.assertIn("python", result["matched_skills"])
        self.assertIn("sql", result["matched_skills"])
        self.assertIn("docker", result["missing_skills"])
        self.assertIn("kubernetes", result["missing_skills"])

    def test_fit_level_strong(self):
        from app.utils.job_gap_analyzer import analyze_job_gap

        report_data = {
            "profile": {"skills": ["python", "sql", "docker"]},
            "match": {},
        }
        job = {"title": "Dev", "skills": ["python", "sql", "docker"]}
        result = analyze_job_gap(report_data, job)
        self.assertEqual(result["fit_level"], "Strong")
        self.assertGreaterEqual(result["fit_score"], 0.65)

    def test_fit_level_weak(self):
        from app.utils.job_gap_analyzer import analyze_job_gap

        report_data = {
            "profile": {"skills": ["excel"]},
            "match": {},
        }
        job = {"title": "Dev", "skills": ["python", "sql", "docker", "flask", "react"]}
        result = analyze_job_gap(report_data, job)
        self.assertEqual(result["fit_level"], "Weak")

    def test_empty_inputs(self):
        from app.utils.job_gap_analyzer import analyze_job_gap

        result = analyze_job_gap(None, None)
        self.assertEqual(result["fit_score"], 0.0)
        self.assertEqual(result["fit_level"], "Weak")

    def test_recommended_focus_populated(self):
        from app.utils.job_gap_analyzer import analyze_job_gap

        report_data = {
            "profile": {"skills": ["python", "sql"]},
            "match": {"target_role": "Engineer"},
        }
        job = {
            "title": "Engineer",
            "skills": ["python", "sql", "docker"],
            "description": "Design and implement scalable systems.",
        }
        result = analyze_job_gap(report_data, job)
        self.assertTrue(len(result["recommended_focus"]) > 0)

    def test_resume_strengths_populated(self):
        from app.utils.job_gap_analyzer import analyze_job_gap

        report_data = {
            "profile": {
                "skills": ["python", "sql", "flask"],
                "experience": ["line1", "line2", "line3"],
            },
            "match": {"target_role": "Backend Developer"},
        }
        job = {"title": "Backend Developer", "skills": ["python", "sql", "flask"]}
        result = analyze_job_gap(report_data, job)
        self.assertTrue(len(result["resume_strengths"]) > 0)


# ── M95 — Session Integration ───────────────────────────────────


class TestJobMatchRouteIntelligence(unittest.TestCase):
    """M95 — /job-match/<job_id> stores intelligence in session."""

    def setUp(self):
        from app import create_app

        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["SECRET_KEY"] = "test-secret"
        self.client = self.app.test_client()

        # Create test user in DB so _ensure_user won't overwrite session tier
        from app.db import db
        from app.models import UserIdentity

        with self.app.app_context():
            if not UserIdentity.query.filter_by(id="test-user").first():
                user = UserIdentity(id="test-user", tier="elite")
                db.session.add(user)
                db.session.commit()

    def test_selecting_job_stores_intelligence(self):
        """After job-match, session should contain selected_job_intelligence."""
        with self.client.session_transaction() as s:
            s["user_id"] = "test-user"
            s["user_tier"] = "elite"
            s["report_data"] = {
                "profile": {"skills": ["python", "sql"], "name": "Test"},
                "match": {"target_role": "Developer"},
            }
            s["tier_usage"] = {}

        # Use an internal dataset job (job id=1 is likely to exist)
        from app.utils.job_data import get_all_jobs

        jobs = get_all_jobs()
        if not jobs:
            self.skipTest("No internal jobs available")
        job_id = jobs[0]["id"]

        resp = self.client.get(f"/job-match/{job_id}", follow_redirects=False)
        self.assertIn(resp.status_code, [302, 303])

        with self.client.session_transaction() as s:
            intel = s.get("selected_job_intelligence")
            gap = s.get("selected_job_gap")
            self.assertIsNotNone(intel)
            self.assertIsNotNone(gap)
            self.assertIn("keywords", intel)
            self.assertIn("fit_score", gap)
            self.assertIn("matched_skills", gap)

    def test_selecting_job_stores_gap(self):
        """After job-match, session should contain selected_job_gap."""
        with self.client.session_transaction() as s:
            s["user_id"] = "test-user"
            s["user_tier"] = "elite"
            s["report_data"] = {
                "profile": {"skills": ["python", "sql"], "name": "Test"},
                "match": {"target_role": "Developer"},
            }
            s["tier_usage"] = {}

        from app.utils.job_data import get_all_jobs

        jobs = get_all_jobs()
        if not jobs:
            self.skipTest("No internal jobs available")
        job_id = jobs[0]["id"]

        self.client.get(f"/job-match/{job_id}", follow_redirects=False)

        with self.client.session_transaction() as s:
            gap = s.get("selected_job_gap")
            self.assertIsNotNone(gap)
            self.assertIn("fit_level", gap)
            self.assertIn("missing_skills", gap)


# ── M96 — Auto-Targeting ────────────────────────────────────────


class TestAutoTargeting(unittest.TestCase):
    """M96 — resume/cover letter targeting with job context."""

    def test_enhance_resume_with_job_context(self):
        from app.utils.resume_enhancer import enhance_resume

        job_context = {
            "title": "Python Developer",
            "company": "TestCo",
            "matched_skills": ["python", "sql"],
            "intelligence": {"required_skills": ["python", "sql", "docker"]},
            "gap": {"recommended_focus": ["system architecture"]},
        }
        result = enhance_resume(
            profile={"skills": ["python", "sql"], "name": "Test User"},
            match={"target_role": "Developer"},
            job_context=job_context,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["target_title"], "Python Developer")
        # Job-targeted skills should appear
        self.assertIn("docker", result["enhanced_skills"])

    def test_enhance_resume_without_job_context(self):
        from app.utils.resume_enhancer import enhance_resume

        result = enhance_resume(
            profile={"skills": ["python", "sql"], "name": "Test User"},
            match={"target_role": "Developer"},
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["target_title"], "Developer")

    def test_cover_letter_with_job_context(self):
        from app.utils.cover_letter_builder import build_cover_letter

        job_context = {
            "title": "Data Analyst",
            "company": "DataCo",
            "matched_skills": ["python", "sql", "statistics"],
            "gap": {"recommended_focus": ["data analysis and insights"]},
        }
        result = build_cover_letter(
            profile={"skills": ["python", "sql"], "name": "Test User"},
            match={"target_role": "Analyst"},
            job_context=job_context,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["target_title"], "Data Analyst")
        self.assertEqual(result["company"], "DataCo")
        # Body should reference matched skills
        body_text = " ".join(result["body_points"])
        self.assertIn("python", body_text.lower())

    def test_cover_letter_without_job_context(self):
        from app.utils.cover_letter_builder import build_cover_letter

        result = build_cover_letter(
            profile={"skills": ["python"], "name": "Test User"},
            match={"target_role": "Developer"},
        )
        self.assertIsNotNone(result)
        self.assertIn("python", result["full_text"].lower())


# ── M97 — UI Panel Visibility ───────────────────────────────────


class TestFitPanelVisibility(unittest.TestCase):
    """M97 — Fit panel only shows when selected job exists."""

    def setUp(self):
        from app import create_app

        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["SECRET_KEY"] = "test-secret"
        self.client = self.app.test_client()

        # Create test user in DB so _ensure_user won't overwrite session tier
        from app.db import db
        from app.models import UserIdentity

        with self.app.app_context():
            if not UserIdentity.query.filter_by(id="test-user").first():
                user = UserIdentity(id="test-user", tier="elite")
                db.session.add(user)
                db.session.commit()

    def test_dashboard_hides_fit_panel_without_selected_job(self):
        """When no job is selected, fit panel should not appear."""
        with self.client.session_transaction() as s:
            s["user_id"] = "test-user"
            s["user_tier"] = "free"
            s["report_data"] = {
                "profile": {"skills": ["python"]},
                "match": {"target_role": "Dev"},
            }
            s["tier_usage"] = {}

        resp = self.client.get("/dashboard")
        html = resp.data.decode()
        self.assertNotIn("Job Fit Analysis", html)

    def test_dashboard_shows_fit_panel_with_selected_job(self):
        """When a job is selected, fit panel should appear."""
        with self.client.session_transaction() as s:
            s["user_id"] = "test-user"
            s["user_tier"] = "elite"
            s["report_data"] = {
                "profile": {"skills": ["python", "sql"]},
                "match": {"target_role": "Developer"},
                "job_context": {
                    "job_id": "test1",
                    "title": "Python Dev",
                    "company": "TestCo",
                    "location": "Remote",
                },
            }
            s["selected_job_intelligence"] = {
                "keywords": ["python"],
                "seniority_hint": "Senior",
                "domain_hint": "Backend",
                "required_skills": ["python"],
                "preferred_skills": [],
                "responsibility_signals": [],
            }
            s["selected_job_gap"] = {
                "fit_score": 0.8,
                "fit_level": "Strong",
                "matched_skills": ["python"],
                "missing_skills": ["docker"],
                "resume_strengths": ["Strong alignment in: python"],
                "resume_gaps": ["Missing required skills: docker"],
                "recommended_focus": ["Highlight proficiency in python"],
            }
            s["tier_usage"] = {}

        resp = self.client.get("/dashboard")
        html = resp.data.decode()
        self.assertIn("Job Fit Analysis", html)
        self.assertIn("Why You Fit", html)
        self.assertIn("What To Improve", html)


# ── Existing Flows Still Work ────────────────────────────────────


class TestExistingFlowsIntact(unittest.TestCase):
    """Verify Bundles A-O flows are not broken."""

    def test_job_intelligence_import(self):
        from app.utils.job_intelligence import extract_job_intelligence

        self.assertTrue(callable(extract_job_intelligence))

    def test_gap_analyzer_import(self):
        from app.utils.job_gap_analyzer import analyze_job_gap

        self.assertTrue(callable(analyze_job_gap))

    def test_app_creates_ok(self):
        from app import create_app

        app = create_app()
        self.assertIsNotNone(app)

    def test_resume_enhancer_backward_compatible(self):
        """enhance_resume works without job_context (backward compat)."""
        from app.utils.resume_enhancer import enhance_resume

        result = enhance_resume(
            profile={"skills": ["python"], "name": "Test"},
            match={"target_role": "Dev"},
        )
        self.assertIsNotNone(result)

    def test_cover_letter_builder_backward_compatible(self):
        """build_cover_letter works without job_context."""
        from app.utils.cover_letter_builder import build_cover_letter

        result = build_cover_letter(
            profile={"skills": ["python"], "name": "Test"},
            match={"target_role": "Dev"},
        )
        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()
