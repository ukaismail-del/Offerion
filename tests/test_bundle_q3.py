"""Tests for Bundle Q3 — Smart Query + Fallback Engine."""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── build_search_query ───────────────────────────────────────────


class TestBuildSearchQuery(unittest.TestCase):
    """Smart query builder extracts role + top keywords."""

    def test_role_only(self):
        from app.utils.job_sources import build_search_query

        q = build_search_query("Data Analyst")
        self.assertEqual(q, "Data Analyst")

    def test_role_plus_resume_keywords(self):
        from app.utils.job_sources import build_search_query

        q = build_search_query("Backend Developer", "I know Python and SQL well")
        self.assertIn("Backend Developer", q)
        self.assertIn("python", q)
        self.assertIn("sql", q)

    def test_max_two_keywords(self):
        from app.utils.job_sources import build_search_query

        big_resume = (
            "Python SQL Java JavaScript React Docker AWS "
            "Kubernetes machine learning data analytics"
        )
        q = build_search_query("Engineer", big_resume)
        # role + at most 2 keywords
        parts = q.split()
        # Remove the role word to count keywords
        kw_parts = [p for p in parts if p.lower() != "engineer"]
        self.assertLessEqual(len(kw_parts), 2)

    def test_empty_role_and_resume(self):
        from app.utils.job_sources import build_search_query

        q = build_search_query("", "")
        self.assertEqual(q, "")

    def test_no_resume(self):
        from app.utils.job_sources import build_search_query

        q = build_search_query("Product Manager", "")
        self.assertEqual(q, "Product Manager")


# ── Fallback Search Logic ────────────────────────────────────────


class TestFallbackSearch(unittest.TestCase):
    """get_unified_jobs falls back when primary query returns nothing."""

    def test_fallback_triggers_on_empty(self):
        from app.utils.job_feed import get_unified_jobs

        call_log = []

        def mock_fetch(query=None, location=None, remote=None, limit=25):
            call_log.append(query)
            if query and "niche" in query.lower():
                return []
            # Return jobs for fallback queries
            return [
                {
                    "id": "fb_1",
                    "title": "Software Engineer",
                    "company": "FallbackCo",
                    "location": "Remote",
                    "skills": ["python"],
                    "source": "external",
                }
            ]

        with patch("app.utils.job_feed.fetch_external_jobs", side_effect=mock_fetch):
            with patch.dict(os.environ, {"USE_STATIC_JOBS": ""}):
                import importlib, app.utils.job_data as jd

                importlib.reload(jd)
                result = get_unified_jobs(
                    query=None,
                    target_role="Niche Specialist",
                    resume_text="I know niche things",
                )
                self.assertGreater(len(result), 0)
                self.assertTrue(result.used_fallback)

    def test_no_fallback_when_primary_succeeds(self):
        from app.utils.job_feed import get_unified_jobs

        call_count = [0]

        def mock_fetch(query=None, location=None, remote=None, limit=25):
            call_count[0] += 1
            return [
                {
                    "id": "ok_1",
                    "title": "Dev",
                    "company": "Co",
                    "location": "Remote",
                    "skills": ["python"],
                    "source": "external",
                }
            ]

        with patch("app.utils.job_feed.fetch_external_jobs", side_effect=mock_fetch):
            with patch.dict(os.environ, {"USE_STATIC_JOBS": ""}):
                import importlib, app.utils.job_data as jd

                importlib.reload(jd)
                result = get_unified_jobs(target_role="Developer")
                self.assertGreater(len(result), 0)
                self.assertFalse(result.used_fallback)
                # Only one call — no fallback needed
                self.assertEqual(call_count[0], 1)

    def test_fallback_uses_target_role_first(self):
        from app.utils.job_feed import get_unified_jobs

        call_log = []

        def mock_fetch(query=None, location=None, remote=None, limit=25):
            call_log.append(query)
            if query and query.strip() == "Data Analyst":
                return [
                    {
                        "id": "da_1",
                        "title": "Data Analyst",
                        "company": "Co",
                        "location": "Remote",
                        "skills": ["sql"],
                        "source": "external",
                    }
                ]
            return []

        with patch("app.utils.job_feed.fetch_external_jobs", side_effect=mock_fetch):
            with patch.dict(os.environ, {"USE_STATIC_JOBS": ""}):
                import importlib, app.utils.job_data as jd

                importlib.reload(jd)
                result = get_unified_jobs(
                    target_role="Data Analyst",
                    resume_text="Python SQL Tableau",
                )
                self.assertGreater(len(result), 0)
                # First fallback should be the target_role itself
                self.assertIn("Data Analyst", call_log)

    def test_used_fallback_attribute_on_list(self):
        from app.utils.job_feed import get_unified_jobs

        with patch("app.utils.job_feed.fetch_external_jobs", return_value=[]):
            with patch.dict(os.environ, {"USE_STATIC_JOBS": ""}):
                import importlib, app.utils.job_data as jd

                importlib.reload(jd)
                result = get_unified_jobs()
                self.assertTrue(hasattr(result, "used_fallback"))


# ── Filter Safety ────────────────────────────────────────────────


class TestFilterSafety(unittest.TestCase):
    """Empty/blank location is NOT sent to the API."""

    def test_empty_location_not_sent(self):
        from app.utils.job_feed import get_unified_jobs

        def mock_fetch(query=None, location=None, remote=None, limit=25):
            # location should be None, not empty string
            self.assertIsNone(location)
            return []

        with patch("app.utils.job_feed.fetch_external_jobs", side_effect=mock_fetch):
            with patch.dict(os.environ, {"USE_STATIC_JOBS": ""}):
                import importlib, app.utils.job_data as jd

                importlib.reload(jd)
                get_unified_jobs(location="")

    def test_whitespace_location_not_sent(self):
        from app.utils.job_feed import get_unified_jobs

        def mock_fetch(query=None, location=None, remote=None, limit=25):
            self.assertIsNone(location)
            return []

        with patch("app.utils.job_feed.fetch_external_jobs", side_effect=mock_fetch):
            with patch.dict(os.environ, {"USE_STATIC_JOBS": ""}):
                import importlib, app.utils.job_data as jd

                importlib.reload(jd)
                get_unified_jobs(location="   ")


# ── Fallback Banner UI ───────────────────────────────────────────


class TestFallbackBannerUI(unittest.TestCase):
    """Dashboard shows fallback banner when broader matches used."""

    def setUp(self):
        os.environ["DATABASE_URL"] = "sqlite://"
        from app import create_app

        self.app = create_app(testing=True)
        self.app.config["SECRET_KEY"] = "test-secret"
        self.client = self.app.test_client()

    def test_fallback_banner_shown(self):
        with self.client.session_transaction() as s:
            s["user_id"] = "test"
            s["user_tier"] = "elite"
            s["report_data"] = {
                "profile": {"skills": ["python"], "experience": []},
                "match": {"target_role": "Niche Role"},
            }
            s["tier_usage"] = {}

        # Mock get_unified_jobs to return a tagged list with used_fallback=True
        from app.utils.job_feed import _TaggedList

        def mock_unified(**kwargs):
            jobs = _TaggedList(
                [
                    {
                        "id": "fb",
                        "title": "Dev",
                        "company": "Co",
                        "location": "Remote",
                        "remote": True,
                        "skills": ["python"],
                        "score": 0.5,
                        "match_level": "Moderate",
                        "matched_skills": ["python"],
                        "missing_skills": [],
                        "freshness_score": 0.5,
                        "posted_at": None,
                        "source": "external",
                        "source_name": "mock",
                        "url": None,
                        "apply_url": None,
                    }
                ]
            )
            jobs.used_fallback = True
            return jobs

        with patch("app.routes.get_unified_jobs", side_effect=mock_unified):
            with patch(
                "app.routes.match_jobs",
                return_value=[
                    {
                        "id": "fb",
                        "title": "Dev",
                        "company": "Co",
                        "location": "Remote",
                        "remote": True,
                        "score": 0.5,
                        "match_level": "Moderate",
                        "matched_skills": ["python"],
                        "missing_skills": [],
                        "freshness_score": 0.5,
                        "posted_at": None,
                        "source": "external",
                        "source_name": "mock",
                        "url": None,
                        "apply_url": None,
                    }
                ],
            ):
                resp = self.client.get("/dashboard")
                html = resp.data.decode()
                self.assertIn("broader matches", html)

    def test_no_banner_without_fallback(self):
        with self.client.session_transaction() as s:
            s["user_id"] = "test"
            s["user_tier"] = "elite"
            s["report_data"] = {
                "profile": {"skills": ["python"], "experience": []},
                "match": {"target_role": "Developer"},
            }
            s["tier_usage"] = {}

        from app.utils.job_feed import _TaggedList

        def mock_unified(**kwargs):
            jobs = _TaggedList([])
            jobs.used_fallback = False
            return jobs

        with patch("app.routes.get_unified_jobs", side_effect=mock_unified):
            with patch("app.routes.match_jobs", return_value=[]):
                resp = self.client.get("/dashboard")
                html = resp.data.decode()
                self.assertNotIn("broader matches", html)


# ── Backward Compatibility ───────────────────────────────────────


class TestBackwardCompat(unittest.TestCase):
    """Existing callers of get_unified_jobs still work."""

    def test_old_signature_works(self):
        """Calling without new params still works."""
        from app.utils.job_feed import get_unified_jobs

        with patch("app.utils.job_feed.fetch_external_jobs", return_value=[]):
            with patch.dict(os.environ, {"USE_STATIC_JOBS": ""}):
                import importlib, app.utils.job_data as jd

                importlib.reload(jd)
                result = get_unified_jobs()
                self.assertIsInstance(result, list)
                self.assertTrue(hasattr(result, "used_fallback"))

    def test_result_is_list_subclass(self):
        from app.utils.job_feed import get_unified_jobs

        with patch("app.utils.job_feed.fetch_external_jobs", return_value=[]):
            result = get_unified_jobs()
            self.assertIsInstance(result, list)
            # Should work with len, indexing, iteration
            self.assertEqual(len(result), len(list(result)))


if __name__ == "__main__":
    unittest.main()
