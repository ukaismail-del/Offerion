"""Tests for Bundle Q2 — Real Job Feed + Dynamic Matching Engine."""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── API / Provider Tests ─────────────────────────────────────────


class TestAutoDetectProvider(unittest.TestCase):
    """_get_provider auto-detects Adzuna when keys are present."""

    def test_auto_detect_adzuna(self):
        from app.utils.job_sources import _get_provider

        with patch.dict(
            os.environ,
            {
                "JOB_SOURCE_PROVIDER": "",
                "ADZUNA_APP_ID": "my_id",
                "ADZUNA_APP_KEY": "my_key",
            },
        ):
            self.assertEqual(_get_provider(), "adzuna")

    def test_no_keys_returns_empty(self):
        from app.utils.job_sources import _get_provider

        with patch.dict(
            os.environ,
            {
                "JOB_SOURCE_PROVIDER": "",
                "ADZUNA_APP_ID": "",
                "ADZUNA_APP_KEY": "",
            },
        ):
            self.assertEqual(_get_provider(), "")

    def test_explicit_provider_honoured(self):
        from app.utils.job_sources import _get_provider

        with patch.dict(os.environ, {"JOB_SOURCE_PROVIDER": "mock"}):
            self.assertEqual(_get_provider(), "mock")

    def test_explicit_none_returns_empty(self):
        from app.utils.job_sources import _get_provider

        with patch.dict(os.environ, {"JOB_SOURCE_PROVIDER": "none"}):
            self.assertEqual(_get_provider(), "")


class TestBuildResumeQuery(unittest.TestCase):
    """build_resume_query creates API query from resume skills."""

    def test_basic(self):
        from app.utils.job_sources import build_resume_query

        q = build_resume_query(["python", "sql", "flask"])
        self.assertEqual(q, "python sql flask")

    def test_max_terms(self):
        from app.utils.job_sources import build_resume_query

        skills = ["python", "sql", "flask", "docker", "aws", "react", "java"]
        q = build_resume_query(skills, max_terms=3)
        self.assertEqual(q, "python sql flask")

    def test_empty(self):
        from app.utils.job_sources import build_resume_query

        self.assertEqual(build_resume_query([]), "")
        self.assertEqual(build_resume_query(None), "")

    def test_filters_not_detected(self):
        from app.utils.job_sources import build_resume_query

        q = build_resume_query(["python", "Not detected", "sql"])
        self.assertNotIn("not detected", q.lower())


class TestMockProviderAPI(unittest.TestCase):
    """Mock provider returns jobs with the right structure."""

    def test_mock_returns_structured_jobs(self):
        from app.utils.job_sources import fetch_external_jobs

        with patch.dict(os.environ, {"JOB_SOURCE_PROVIDER": "mock"}):
            jobs = fetch_external_jobs()
            self.assertGreater(len(jobs), 0)
            for j in jobs:
                self.assertIn("title", j)
                self.assertIn("company", j)
                self.assertIn("skills", j)
                self.assertIn("url", j)
                self.assertEqual(j["source"], "external")


class TestAdzunaAPIIntegration(unittest.TestCase):
    """Adzuna adapter works with mocked HTTP."""

    @patch("app.utils.job_sources._adzuna_http_request")
    def test_adzuna_returns_normalised(self, mock_http):
        from app.utils.job_sources import fetch_external_jobs

        mock_http.return_value = {
            "results": [
                {
                    "id": "99",
                    "title": "Python Developer",
                    "company": {"display_name": "APICo"},
                    "location": {"area": ["US", "CA", "SF"]},
                    "description": "Build Python apps with Flask and SQL.",
                    "created": "2025-12-01T00:00:00Z",
                    "redirect_url": "https://adzuna.com/apply/99",
                }
            ]
        }
        with patch.dict(
            os.environ,
            {
                "JOB_SOURCE_PROVIDER": "adzuna",
                "ADZUNA_APP_ID": "test",
                "ADZUNA_APP_KEY": "test",
            },
        ):
            jobs = fetch_external_jobs(query="python")
            self.assertEqual(len(jobs), 1)
            j = jobs[0]
            self.assertEqual(j["title"], "Python Developer")
            self.assertEqual(j["source"], "external")
            self.assertIn("python", j["skills"])
            self.assertIn("flask", j["skills"])

    def test_api_failure_returns_empty(self):
        from app.utils.job_sources import fetch_external_jobs

        with patch.dict(
            os.environ,
            {
                "JOB_SOURCE_PROVIDER": "adzuna",
                "ADZUNA_APP_ID": "test",
                "ADZUNA_APP_KEY": "test",
            },
        ):
            with patch(
                "app.utils.job_sources._adzuna_http_request",
                side_effect=Exception("Network error"),
            ):
                jobs = fetch_external_jobs(query="python")
                self.assertEqual(jobs, [])


# ── Static Data Removal Tests ────────────────────────────────────


class TestStaticDataRemoval(unittest.TestCase):
    """get_all_jobs returns empty by default (API-first mode)."""

    def test_get_all_jobs_empty_by_default(self):
        with patch.dict(os.environ, {"USE_STATIC_JOBS": ""}, clear=False):
            import importlib
            import app.utils.job_data as jd

            importlib.reload(jd)
            self.assertEqual(jd.get_all_jobs(), [])

    def test_get_all_jobs_enabled_with_env(self):
        with patch.dict(os.environ, {"USE_STATIC_JOBS": "true"}, clear=False):
            import importlib
            import app.utils.job_data as jd

            importlib.reload(jd)
            jobs = jd.get_all_jobs()
            self.assertGreater(len(jobs), 0)

    def test_get_static_jobs_always_returns(self):
        from app.utils.job_data import get_static_jobs

        jobs = get_static_jobs()
        self.assertGreater(len(jobs), 0)

    def test_find_job_by_id_still_works(self):
        from app.utils.job_data import find_job_by_id

        job = find_job_by_id("job_1")
        self.assertIsNotNone(job)
        self.assertEqual(job["title"], "Backend Engineer")


# ── Matching Logic Tests ─────────────────────────────────────────


class TestMatchingLogic(unittest.TestCase):
    """Skill-overlap-driven matching with correct scoring."""

    def test_full_overlap_high_score(self):
        from app.utils.job_matcher import match_jobs

        report = {
            "profile": {
                "skills": ["python", "flask", "sql", "docker", "api"],
                "experience": [],
            },
            "match": {"target_role": "Backend Engineer"},
        }
        jobs = [
            {
                "id": "t1",
                "title": "Backend Engineer",
                "company": "Co",
                "skills": ["python", "flask", "sql", "docker", "api"],
            }
        ]
        results = match_jobs(report, jobs=jobs)
        self.assertEqual(len(results), 1)
        # Full skill overlap (5/5 = 1.0 * 0.70) + title overlap → high score
        self.assertGreaterEqual(results[0]["score"], 0.75)

    def test_no_overlap_low_score(self):
        from app.utils.job_matcher import match_jobs

        report = {
            "profile": {
                "skills": ["java", "spring", "maven"],
                "experience": [],
            },
            "match": {"target_role": "Java Developer"},
        }
        jobs = [
            {
                "id": "t2",
                "title": "Frontend Designer",
                "company": "Co",
                "skills": ["figma", "css", "html", "prototyping"],
            }
        ]
        results = match_jobs(report, jobs=jobs)
        # No skill overlap → very low score
        if results:
            self.assertLess(results[0]["score"], 0.20)

    def test_partial_overlap_moderate(self):
        from app.utils.job_matcher import match_jobs

        report = {
            "profile": {
                "skills": ["python", "sql", "excel"],
                "experience": [],
            },
            "match": {"target_role": "Data Analyst"},
        }
        jobs = [
            {
                "id": "t3",
                "title": "Data Analyst",
                "company": "Co",
                "skills": [
                    "python",
                    "sql",
                    "excel",
                    "tableau",
                    "statistics",
                    "reporting",
                ],
            }
        ]
        results = match_jobs(report, jobs=jobs)
        self.assertEqual(len(results), 1)
        # 3/6 overlap = 0.5 * 0.70 = 0.35 + title bonus
        self.assertGreaterEqual(results[0]["score"], 0.35)
        self.assertLessEqual(results[0]["score"], 0.70)

    def test_score_is_percentage_of_job_skills(self):
        """Core formula: overlapping / job_required_skills."""
        from app.utils.job_matcher import match_jobs

        report = {
            "profile": {"skills": ["python", "sql"], "experience": []},
            "match": {"target_role": "Eng"},
        }
        jobs = [
            {
                "id": "ratio1",
                "title": "Eng",
                "company": "X",
                "skills": ["python", "sql", "docker", "aws"],
            }
        ]
        results = match_jobs(report, jobs=jobs)
        self.assertEqual(len(results), 1)
        # skill_score = 2/4 = 0.5
        # weighted = 0.5 * 0.70 = 0.35 (plus small title/freshness bonuses)
        self.assertGreaterEqual(results[0]["score"], 0.30)


# ── Different Resumes → Different Results ────────────────────────


class TestDifferentResumesProduceDifferentResults(unittest.TestCase):
    """Different resumes produce different match scores and orderings."""

    def _jobs(self):
        return [
            {
                "id": "j1",
                "title": "Python Backend Developer",
                "company": "A",
                "skills": ["python", "flask", "sql", "docker", "api"],
            },
            {
                "id": "j2",
                "title": "Frontend Designer",
                "company": "B",
                "skills": ["react", "css", "javascript", "figma", "html"],
            },
            {
                "id": "j3",
                "title": "Data Scientist",
                "company": "C",
                "skills": [
                    "python",
                    "machine learning",
                    "tensorflow",
                    "sql",
                    "statistics",
                ],
            },
        ]

    def test_python_dev_gets_backend_first(self):
        from app.utils.job_matcher import match_jobs

        report = {
            "profile": {
                "skills": ["python", "flask", "sql", "docker"],
                "experience": [],
            },
            "match": {"target_role": "Backend Developer"},
        }
        results = match_jobs(report, jobs=self._jobs())
        self.assertGreater(len(results), 0)
        # Backend job should rank first for python/flask resume
        self.assertEqual(results[0]["id"], "j1")

    def test_designer_gets_frontend_first(self):
        from app.utils.job_matcher import match_jobs

        report = {
            "profile": {
                "skills": ["react", "css", "javascript", "figma", "html"],
                "experience": [],
            },
            "match": {"target_role": "Frontend Designer"},
        }
        results = match_jobs(report, jobs=self._jobs())
        self.assertGreater(len(results), 0)
        # Frontend job should rank first for design resume
        self.assertEqual(results[0]["id"], "j2")

    def test_different_resumes_different_scores(self):
        from app.utils.job_matcher import match_jobs

        report_py = {
            "profile": {"skills": ["python", "flask", "sql"], "experience": []},
            "match": {"target_role": "Developer"},
        }
        report_js = {
            "profile": {"skills": ["react", "javascript", "css"], "experience": []},
            "match": {"target_role": "Developer"},
        }
        jobs = self._jobs()
        results_py = match_jobs(report_py, jobs=jobs)
        results_js = match_jobs(report_js, jobs=jobs)
        # Same job set, different scores
        scores_py = {r["id"]: r["score"] for r in results_py}
        scores_js = {r["id"]: r["score"] for r in results_js}
        self.assertNotEqual(scores_py, scores_js)


# ── Sorting Tests ────────────────────────────────────────────────


class TestSorting(unittest.TestCase):
    """Results sorted by score descending, limited to 20."""

    def test_sorted_descending(self):
        from app.utils.job_matcher import match_jobs

        report = {
            "profile": {"skills": ["python", "sql", "flask"], "experience": []},
            "match": {"target_role": "Engineer"},
        }
        from app.utils.job_data import get_static_jobs

        results = match_jobs(report, jobs=get_static_jobs())
        self.assertGreater(len(results), 1)
        for i in range(len(results) - 1):
            self.assertGreaterEqual(results[i]["score"], results[i + 1]["score"])

    def test_default_limit_20(self):
        from app.utils.job_matcher import match_jobs

        report = {
            "profile": {"skills": ["python", "sql", "flask"], "experience": []},
            "match": {"target_role": "Engineer"},
        }
        from app.utils.job_data import get_static_jobs

        results = match_jobs(report, jobs=get_static_jobs())
        self.assertLessEqual(len(results), 20)


# ── Skill Extraction Tests ───────────────────────────────────────


class TestSkillExtraction(unittest.TestCase):
    """Skills extracted from job descriptions."""

    def test_extract_from_description(self):
        from app.utils.job_sources import extract_skills_from_text

        text = "Experience with React, JavaScript, and REST APIs in a CI/CD environment"
        skills = extract_skills_from_text(text)
        self.assertIn("react", skills)
        self.assertIn("javascript", skills)
        self.assertIn("ci/cd", skills)

    def test_no_duplicates(self):
        from app.utils.job_sources import extract_skills_from_text

        text = "Python Python python PYTHON developer with python experience"
        skills = extract_skills_from_text(text)
        self.assertEqual(skills.count("python"), 1)


# ── Resume-Driven Query Tests ────────────────────────────────────


class TestResumeDrivenQuery(unittest.TestCase):
    """get_unified_jobs uses resume skills for API query."""

    def test_resume_skills_passed_to_api(self):
        from app.utils.job_feed import get_unified_jobs

        with patch("app.utils.job_feed.fetch_external_jobs") as mock_fetch:
            mock_fetch.return_value = [
                {
                    "id": "api_1",
                    "title": "Python Dev",
                    "company": "APICo",
                    "location": "Remote",
                    "skills": ["python"],
                    "source": "external",
                }
            ]
            jobs = get_unified_jobs(resume_skills=["python", "sql"])
            # fetch_external_jobs should have been called with a query
            call_kwargs = mock_fetch.call_args
            self.assertIn(
                "python",
                call_kwargs.kwargs.get("query", "") or call_kwargs[1].get("query", ""),
            )

    def test_explicit_query_overrides_resume_skills(self):
        from app.utils.job_feed import get_unified_jobs

        with patch("app.utils.job_feed.fetch_external_jobs") as mock_fetch:
            mock_fetch.return_value = []
            get_unified_jobs(query="react developer", resume_skills=["python", "sql"])
            call_kwargs = mock_fetch.call_args
            query_used = call_kwargs.kwargs.get("query", "") or call_kwargs[1].get(
                "query", ""
            )
            self.assertEqual(query_used, "react developer")


# ── No Static Jobs in Production ─────────────────────────────────


class TestNoStaticJobsInProduction(unittest.TestCase):
    """Unified feed returns no static jobs when USE_STATIC_JOBS is not set."""

    def test_no_static_without_env(self):
        from app.utils.job_feed import get_unified_jobs

        with patch.dict(
            os.environ,
            {
                "JOB_SOURCE_PROVIDER": "",
                "ADZUNA_APP_ID": "",
                "ADZUNA_APP_KEY": "",
                "USE_STATIC_JOBS": "",
            },
        ):
            import importlib
            import app.utils.job_data as jd

            importlib.reload(jd)
            jobs = get_unified_jobs()
            self.assertEqual(jobs, [])

    def test_mock_provider_only_external(self):
        """With mock provider and no static jobs, only external jobs returned."""
        from app.utils.job_feed import get_unified_jobs

        with patch.dict(
            os.environ,
            {
                "JOB_SOURCE_PROVIDER": "mock",
                "USE_STATIC_JOBS": "",
            },
        ):
            import importlib
            import app.utils.job_data as jd

            importlib.reload(jd)
            jobs = get_unified_jobs(limit=100)
            sources = {j.get("source") for j in jobs}
            self.assertEqual(sources, {"external"})


if __name__ == "__main__":
    unittest.main()
