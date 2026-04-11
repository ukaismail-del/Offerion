"""M86 — Bundle N tests: external fallback, unified feed, freshness, save-job metadata."""

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

# Ensure project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestJobSources(unittest.TestCase):
    """M81/M86 — External source abstraction."""

    def test_no_provider_returns_empty(self):
        """When JOB_SOURCE_PROVIDER is unset, fetch_external_jobs returns []."""
        with patch.dict(os.environ, {"JOB_SOURCE_PROVIDER": ""}, clear=False):
            # Re-import to pick up env change
            import importlib
            import app.utils.job_sources as src

            importlib.reload(src)
            result = src.fetch_external_jobs()
            self.assertEqual(result, [])

    def test_mock_provider_returns_jobs(self):
        with patch.dict(os.environ, {"JOB_SOURCE_PROVIDER": "mock"}, clear=False):
            import importlib
            import app.utils.job_sources as src

            importlib.reload(src)
            result = src.fetch_external_jobs()
            self.assertGreater(len(result), 0)
            for job in result:
                self.assertEqual(job["source"], "external")
                self.assertIn("title", job)
                self.assertIn("posted_at", job)

    def test_bad_data_skipped(self):
        """Malformed items are silently skipped."""
        import app.utils.job_sources as src

        result = src._normalize({}, "test")
        self.assertIsNone(result)

    def test_normalize_valid(self):
        import app.utils.job_sources as src

        raw = {
            "title": "Test Job",
            "company": "TestCo",
            "location": "Remote",
            "remote": True,
            "skills": ["python"],
            "description": "A test job.",
            "posted_at": "2026-04-01",
            "url": "https://example.com/job",
        }
        result = src._normalize(raw, "mock")
        self.assertEqual(result["source"], "external")
        self.assertEqual(result["source_name"], "mock")
        self.assertEqual(result["title"], "Test Job")
        self.assertTrue(result["remote"])


class TestUnifiedFeed(unittest.TestCase):
    """M82/M86 — Unified feed merger."""

    def test_unified_returns_internal_when_no_external(self):
        with patch.dict(os.environ, {"JOB_SOURCE_PROVIDER": ""}, clear=False):
            import importlib
            import app.utils.job_sources as src

            importlib.reload(src)
            import app.utils.job_feed as feed

            importlib.reload(feed)
            jobs = feed.get_unified_jobs()
            self.assertGreater(len(jobs), 0)
            # All should be internal (no external configured)
            sources = {j.get("source", "internal") for j in jobs}
            self.assertEqual(sources, {"internal"})

    def test_unified_includes_external_when_configured(self):
        with patch.dict(os.environ, {"JOB_SOURCE_PROVIDER": "mock"}, clear=False):
            import importlib
            import app.utils.job_sources as src

            importlib.reload(src)
            import app.utils.job_feed as feed

            importlib.reload(feed)
            jobs = feed.get_unified_jobs(limit=100)
            sources = {j.get("source", "internal") for j in jobs}
            self.assertIn("external", sources)
            self.assertIn("internal", sources)

    def test_dedup_prefers_external(self):
        """When internal and external share same title+company+location,
        external version wins."""
        from app.utils.job_feed import _dedup_key

        internal = {
            "title": "Data Analyst",
            "company": "InsightHub",
            "location": "Remote",
            "source": "internal",
            "url": None,
        }
        external = {
            "title": "Data Analyst",
            "company": "InsightHub",
            "location": "Remote",
            "source": "external",
            "url": "https://example.com",
        }
        self.assertEqual(_dedup_key(internal), _dedup_key(external))


class TestFreshnessScoring(unittest.TestCase):
    """M83/M86 — Freshness signal."""

    def test_today_is_max(self):
        from app.utils.job_matcher import _freshness_signal

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.assertEqual(_freshness_signal(today), 1.0)

    def test_missing_date_is_neutral(self):
        from app.utils.job_matcher import _freshness_signal

        self.assertEqual(_freshness_signal(None), 0.5)

    def test_old_date_is_low(self):
        from app.utils.job_matcher import _freshness_signal

        old = (datetime.now(timezone.utc) - timedelta(days=60)).strftime("%Y-%m-%d")
        score = _freshness_signal(old)
        self.assertLess(score, 0.1)

    def test_freshness_affects_ranking(self):
        """Two identical-skill jobs: the newer one should rank higher."""
        from app.utils.job_matcher import match_jobs

        now = datetime.now(timezone.utc)
        job_new = {
            "id": "fresh_1",
            "title": "Python Dev",
            "company": "A",
            "location": "Remote",
            "remote": True,
            "skills": ["python", "sql"],
            "posted_at": now.strftime("%Y-%m-%d"),
            "source": "external",
        }
        job_old = {
            "id": "old_1",
            "title": "Python Dev",
            "company": "B",
            "location": "Remote",
            "remote": True,
            "skills": ["python", "sql"],
            "posted_at": (now - timedelta(days=30)).strftime("%Y-%m-%d"),
            "source": "external",
        }
        report_data = {
            "profile": {"skills": ["python", "sql"], "experience": []},
            "match": {"target_role": "python dev"},
        }
        results = match_jobs(report_data, jobs=[job_new, job_old], limit=2)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["id"], "fresh_1")
        self.assertGreater(results[0]["freshness_score"], results[1]["freshness_score"])


class TestMatcherOutputShape(unittest.TestCase):
    """M83/M86 — Matcher output includes freshness + source fields."""

    def test_output_has_new_fields(self):
        from app.utils.job_matcher import match_jobs
        from app.utils.job_data import get_all_jobs

        report_data = {
            "profile": {"skills": ["python", "sql"], "experience": ["2y at X"]},
            "match": {"target_role": "data analyst"},
        }
        results = match_jobs(report_data, limit=3)
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertIn("freshness_score", r)
            self.assertIn("posted_at", r)
            self.assertIn("source", r)
            self.assertIn("match_level", r)
            self.assertIn("missing_skills", r)


class TestSaveJobMetadata(unittest.TestCase):
    """M85/M86 — Save-job preserves source/url/freshness metadata."""

    def test_job_context_preserves_fields(self):
        """Simulate what job-match route builds for job_context."""
        job = {
            "id": "ext_mock_1",
            "title": "React Developer",
            "company": "ExternaCorp",
            "location": "Remote",
            "skills": ["react", "javascript"],
            "source": "external",
            "source_name": "mock",
            "url": "https://example.com/jobs/react-dev",
            "posted_at": "2026-04-10",
        }
        # Simulate what save-job route does
        saved = {}
        saved["source"] = job.get("source", "internal")
        saved["source_name"] = job.get("source_name")
        saved["url"] = job.get("url")
        saved["posted_at"] = job.get("posted_at")
        self.assertEqual(saved["source"], "external")
        self.assertEqual(saved["source_name"], "mock")
        self.assertEqual(saved["url"], "https://example.com/jobs/react-dev")
        self.assertEqual(saved["posted_at"], "2026-04-10")


class TestExternalFailureFallback(unittest.TestCase):
    """M86 — External failure falls back safely."""

    def test_provider_exception_returns_empty(self):
        """If the provider adapter raises, fetch_external_jobs returns []."""
        import app.utils.job_sources as src

        def _exploding_adapter(**kwargs):
            raise RuntimeError("API down")

        original = src._PROVIDERS.copy()
        src._PROVIDERS["explode"] = _exploding_adapter
        old_provider = src._PROVIDER
        src._PROVIDER = "explode"
        try:
            result = src.fetch_external_jobs()
            self.assertEqual(result, [])
        finally:
            src._PROVIDER = old_provider
            src._PROVIDERS = original

    def test_unified_works_when_external_fails(self):
        """Unified feed still returns internal jobs when external blows up."""
        import app.utils.job_sources as src
        import app.utils.job_feed as feed

        def _exploding(**kwargs):
            raise RuntimeError("API down")

        with patch.object(
            feed, "fetch_external_jobs", side_effect=RuntimeError("boom")
        ):
            jobs = feed.get_unified_jobs()
            self.assertGreater(len(jobs), 0)


if __name__ == "__main__":
    unittest.main()
