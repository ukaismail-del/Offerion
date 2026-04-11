"""M81 — External Job Source Abstraction.

Provider abstraction layer for external job sources.
Uses env-driven source toggles.  When no external provider is configured
the module returns an empty list so the app falls back to internal jobs
without crashing.

Architecture allows swapping in a real API (e.g. RapidAPI JSearch)
by implementing a new adapter function and registering it in _PROVIDERS.
"""

import logging
import os
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# ── env config ────────────────────────────────────────────────────
_PROVIDER = os.environ.get("JOB_SOURCE_PROVIDER", "").strip().lower()
_API_KEY = os.environ.get("RAPIDAPI_KEY", "").strip()


# ── helpers ───────────────────────────────────────────────────────

def _normalize(raw, source_name):
    """Normalise a raw dict to the canonical external-job shape.

    Returns *None* if required fields are missing so callers can skip it.
    """
    title = (raw.get("title") or "").strip()
    company = (raw.get("company") or "").strip()
    if not title or not company:
        return None

    return {
        "id": raw.get("id") or f"ext_{source_name}_{hash(title + company) & 0xFFFFFFFF:08x}",
        "source": "external",
        "source_name": source_name,
        "title": title,
        "company": company,
        "location": (raw.get("location") or "").strip(),
        "remote": bool(raw.get("remote")),
        "skills": list(raw.get("skills") or []),
        "description": (raw.get("description") or "").strip(),
        "posted_at": raw.get("posted_at") or None,
        "url": raw.get("url") or None,
    }


# ── mock adapter (for testing / demo) ────────────────────────────

def _fetch_mock(query=None, location=None, remote=None, limit=25):
    """Return deterministic mock external jobs.

    Activated by setting ``JOB_SOURCE_PROVIDER=mock``.
    """
    now = datetime.now(timezone.utc)
    mock_jobs = [
        {
            "id": "ext_mock_1",
            "title": "React Developer",
            "company": "ExternaCorp",
            "location": "Remote",
            "remote": True,
            "skills": ["react", "javascript", "typescript", "css", "api"],
            "description": "Build modern React applications for enterprise SaaS.",
            "posted_at": (now - timedelta(days=1)).strftime("%Y-%m-%d"),
            "url": "https://example.com/jobs/react-dev",
        },
        {
            "id": "ext_mock_2",
            "title": "Python Backend Engineer",
            "company": "RemoteFirst Ltd",
            "location": "Remote",
            "remote": True,
            "skills": ["python", "flask", "sql", "docker", "api"],
            "description": "Design and maintain backend micro-services.",
            "posted_at": (now - timedelta(days=3)).strftime("%Y-%m-%d"),
            "url": "https://example.com/jobs/python-be",
        },
        {
            "id": "ext_mock_3",
            "title": "Data Analyst",
            "company": "NumWorks",
            "location": "Chicago, IL",
            "remote": False,
            "skills": ["python", "sql", "excel", "tableau", "statistics"],
            "description": "Analyse data and produce dashboards for stakeholders.",
            "posted_at": (now - timedelta(days=10)).strftime("%Y-%m-%d"),
            "url": "https://example.com/jobs/data-analyst",
        },
        {
            "id": "ext_mock_4",
            "title": "DevOps Engineer",
            "company": "CloudScale",
            "location": "Austin, TX",
            "remote": False,
            "skills": ["docker", "kubernetes", "aws", "ci/cd", "linux"],
            "description": "Manage CI/CD and cloud infrastructure.",
            "posted_at": (now - timedelta(days=0)).strftime("%Y-%m-%d"),
            "url": "https://example.com/jobs/devops",
        },
        {
            "id": "ext_mock_5",
            "title": "Marketing Manager",
            "company": "GrowFast",
            "location": "Remote",
            "remote": True,
            "skills": ["digital marketing", "seo", "analytics", "content strategy"],
            "description": "Lead growth marketing initiatives.",
            "posted_at": (now - timedelta(days=14)).strftime("%Y-%m-%d"),
            "url": "https://example.com/jobs/marketing-mgr",
        },
    ]

    results = mock_jobs

    if remote is not None:
        results = [j for j in results if j.get("remote") is remote]

    if location:
        loc = location.lower().strip()
        results = [j for j in results if loc in j.get("location", "").lower()]

    if query:
        q = query.lower().strip()
        results = [
            j for j in results
            if q in " ".join([
                j.get("title", ""),
                j.get("company", ""),
                " ".join(j.get("skills", [])),
            ]).lower()
        ]

    return results[:limit]


# ── provider registry ────────────────────────────────────────────
# To add a real provider, create an adapter function matching the
# signature of _fetch_mock and register it below.

_PROVIDERS = {
    "mock": _fetch_mock,
}


# ── public API ────────────────────────────────────────────────────

def fetch_external_jobs(query=None, location=None, remote=None, limit=25):
    """Return normalised jobs from configured external sources.

    Falls back to an empty list when no source is configured or the
    provider raises an exception.
    """
    if not _PROVIDER or _PROVIDER not in _PROVIDERS:
        return []

    adapter = _PROVIDERS[_PROVIDER]
    try:
        raw_jobs = adapter(query=query, location=location, remote=remote, limit=limit)
    except Exception:
        logger.exception("External job source '%s' failed", _PROVIDER)
        return []

    normalised = []
    for raw in raw_jobs:
        try:
            item = _normalize(raw, _PROVIDER)
            if item:
                normalised.append(item)
        except Exception:
            logger.warning("Skipped malformed external job entry")
            continue

    return normalised[:limit]
