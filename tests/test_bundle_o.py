"""Tests for Bundle O — Real Provider Integration + Apply Pipeline (M87-M92)."""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Ensure app root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestSkillExtraction(unittest.TestCase):
    """M88 — extract_skills_from_text."""

    def test_extracts_known_skills(self):
        from app.utils.job_sources import extract_skills_from_text

        result = extract_skills_from_text("Looking for a Python and SQL developer")
        self.assertIn("python", result)
        self.assertIn("sql", result)

    def test_multiword_skills(self):
        from app.utils.job_sources import extract_skills_from_text

        result = extract_skills_from_text(
            "Must have machine learning and digital marketing experience"
        )
        self.assertIn("machine learning", result)
        self.assertIn("digital marketing", result)

    def test_empty_text_returns_empty(self):
        from app.utils.job_sources import extract_skills_from_text

        self.assertEqual(extract_skills_from_text(""), [])
        self.assertEqual(extract_skills_from_text(None), [])

    def test_no_duplicates(self):
        from app.utils.job_sources import extract_skills_from_text

        result = extract_skills_from_text("python python python sql sql")
        self.assertEqual(result, sorted(set(result)))

    def test_case_insensitive(self):
        from app.utils.job_sources import extract_skills_from_text

        result = extract_skills_from_text("PYTHON and React and Docker")
        self.assertIn("python", result)
        self.assertIn("react", result)
        self.assertIn("docker", result)


class TestNormalizeApplyUrl(unittest.TestCase):
    """M87 — _normalize includes apply_url field."""

    def test_apply_url_present(self):
        from app.utils.job_sources import _normalize

        raw = {
            "title": "Dev",
            "company": "Co",
            "apply_url": "https://apply.example.com",
            "url": "https://listing.example.com",
        }
        result = _normalize(raw, "test")
        self.assertEqual(result["apply_url"], "https://apply.example.com")

    def test_apply_url_falls_back_to_url(self):
        from app.utils.job_sources import _normalize

        raw = {"title": "Dev", "company": "Co", "url": "https://listing.example.com"}
        result = _normalize(raw, "test")
        self.assertEqual(result["apply_url"], "https://listing.example.com")

    def test_apply_url_none_when_no_urls(self):
        from app.utils.job_sources import _normalize

        raw = {"title": "Dev", "company": "Co"}
        result = _normalize(raw, "test")
        self.assertIsNone(result["apply_url"])

    def test_skills_extracted_when_missing(self):
        from app.utils.job_sources import _normalize

        raw = {
            "title": "Python Developer",
            "company": "Co",
            "description": "Work with Django and SQL databases",
        }
        result = _normalize(raw, "test")
        self.assertIn("python", result["skills"])
        self.assertIn("django", result["skills"])
        self.assertIn("sql", result["skills"])


class TestAdzunaAdapter(unittest.TestCase):
    """M87 — Adzuna adapter env-gating and response handling."""

    def test_missing_credentials_returns_empty(self):
        from app.utils.job_sources import _fetch_adzuna

        with patch.dict(os.environ, {"ADZUNA_APP_ID": "", "ADZUNA_APP_KEY": ""}):
            result = _fetch_adzuna(query="python")
            self.assertEqual(result, [])

    @patch("app.utils.job_sources._adzuna_http_request")
    def test_parses_adzuna_response(self, mock_http):
        from app.utils.job_sources import _fetch_adzuna

        mock_http.return_value = {
            "results": [
                {
                    "id": "12345",
                    "title": "Python Developer",
                    "company": {"display_name": "TestCo"},
                    "location": {"area": ["US", "California", "San Francisco"]},
                    "description": "Write Python code with Django and SQL.",
                    "created": "2024-01-15T00:00:00Z",
                    "redirect_url": "https://adzuna.com/apply/12345",
                }
            ]
        }
        with patch.dict(
            os.environ, {"ADZUNA_APP_ID": "test_id", "ADZUNA_APP_KEY": "test_key"}
        ):
            result = _fetch_adzuna(query="python")
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["title"], "Python Developer")
            self.assertEqual(result[0]["company"], "TestCo")
            self.assertEqual(result[0]["apply_url"], "https://adzuna.com/apply/12345")
            self.assertIn("San Francisco", result[0]["location"])

    @patch("app.utils.job_sources._adzuna_http_request")
    def test_remote_filter(self, mock_http):
        from app.utils.job_sources import _fetch_adzuna

        mock_http.return_value = {
            "results": [
                {
                    "id": "1",
                    "title": "Remote Python Dev",
                    "company": {"display_name": "Co1"},
                    "location": {"area": []},
                    "description": "Remote role.",
                    "created": "2024-01-15T00:00:00Z",
                },
                {
                    "id": "2",
                    "title": "Onsite Java Dev",
                    "company": {"display_name": "Co2"},
                    "location": {"area": ["US", "NY"]},
                    "description": "Office based.",
                    "created": "2024-01-15T00:00:00Z",
                },
            ]
        }
        with patch.dict(
            os.environ, {"ADZUNA_APP_ID": "test_id", "ADZUNA_APP_KEY": "test_key"}
        ):
            remote_only = _fetch_adzuna(query="dev", remote=True)
            self.assertTrue(all(j["remote"] for j in remote_only))


class TestProviderFallback(unittest.TestCase):
    """M87 — Provider env gating."""

    def test_empty_provider_returns_empty(self):
        from app.utils.job_sources import fetch_external_jobs

        with patch.dict(
            os.environ,
            {"JOB_SOURCE_PROVIDER": "", "ADZUNA_APP_ID": "", "ADZUNA_APP_KEY": ""},
        ):
            result = fetch_external_jobs()
            self.assertEqual(result, [])

    def test_none_provider_returns_empty(self):
        from app.utils.job_sources import fetch_external_jobs

        with patch.dict(os.environ, {"JOB_SOURCE_PROVIDER": "none"}):
            result = fetch_external_jobs()
            self.assertEqual(result, [])

    def test_unknown_provider_returns_empty(self):
        from app.utils.job_sources import fetch_external_jobs

        with patch.dict(os.environ, {"JOB_SOURCE_PROVIDER": "bogus_provider"}):
            result = fetch_external_jobs()
            self.assertEqual(result, [])

    def test_mock_provider_returns_jobs(self):
        from app.utils.job_sources import fetch_external_jobs

        with patch.dict(os.environ, {"JOB_SOURCE_PROVIDER": "mock"}):
            result = fetch_external_jobs()
            self.assertTrue(len(result) > 0)
            for job in result:
                self.assertIn("apply_url", job)


class TestSourceFilter(unittest.TestCase):
    """M91 — Source filter in get_unified_jobs."""

    def test_filter_internal_only(self):
        from app.utils.job_feed import get_unified_jobs

        with patch.dict(
            os.environ, {"JOB_SOURCE_PROVIDER": "mock", "USE_STATIC_JOBS": "true"}
        ):
            import importlib, app.utils.job_data as jd

            importlib.reload(jd)
            internal = get_unified_jobs(source="internal", limit=100)
            for j in internal:
                self.assertEqual(j.get("source"), "internal")

    def test_filter_external_only(self):
        from app.utils.job_feed import get_unified_jobs

        with patch.dict(os.environ, {"JOB_SOURCE_PROVIDER": "mock"}):
            external = get_unified_jobs(source="external", limit=100)
            for j in external:
                self.assertEqual(j.get("source"), "external")

    def test_no_source_filter_returns_both(self):
        from app.utils.job_feed import get_unified_jobs

        with patch.dict(
            os.environ, {"JOB_SOURCE_PROVIDER": "mock", "USE_STATIC_JOBS": "true"}
        ):
            import importlib, app.utils.job_data as jd

            importlib.reload(jd)
            all_jobs = get_unified_jobs(source=None, limit=100)
            sources = {j.get("source") for j in all_jobs}
            self.assertIn("internal", sources)
            self.assertIn("external", sources)


class TestApplyRoute(unittest.TestCase):
    """M89 — /apply/<job_id> route."""

    def setUp(self):
        from app import create_app

        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["SECRET_KEY"] = "test-secret"
        self.client = self.app.test_client()

    def test_apply_missing_job_redirects(self):
        """Unknown job_id redirects to dashboard."""
        with self.client.session_transaction() as s:
            s["user_id"] = "test-user"
        resp = self.client.get("/apply/nonexistent_job_999", follow_redirects=False)
        self.assertIn(resp.status_code, [302, 303])

    def test_apply_mock_job_redirects_to_url(self):
        """Mock job with apply_url should trigger external redirect."""
        with patch.dict(os.environ, {"JOB_SOURCE_PROVIDER": "mock"}):
            with self.client.session_transaction() as s:
                s["user_id"] = "test-user"
            resp = self.client.get("/apply/ext_mock_1", follow_redirects=False)
            self.assertEqual(resp.status_code, 302)
            self.assertIn("example.com/apply/react-dev", resp.location)


class TestMatcherApplyUrl(unittest.TestCase):
    """M87 — match_jobs passes through apply_url."""

    def test_apply_url_in_match_results(self):
        from app.utils.job_matcher import match_jobs

        report_data = {
            "profile": {"skills": ["python", "sql"]},
            "match": {"target_role": "Engineer"},
        }
        jobs = [
            {
                "id": "test1",
                "title": "Python Engineer",
                "company": "Co",
                "skills": ["python", "sql"],
                "apply_url": "https://apply.test.com/1",
                "url": "https://listing.test.com/1",
            }
        ]
        results = match_jobs(report_data, jobs=jobs)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["apply_url"], "https://apply.test.com/1")


if __name__ == "__main__":
    unittest.main()
