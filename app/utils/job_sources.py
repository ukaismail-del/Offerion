"""M81/M87/M88 — External Job Source Abstraction.

Provider abstraction layer for external job sources.
Uses env-driven source toggles.  When no external provider is configured
the module returns an empty list so the app falls back to internal jobs
without crashing.

Providers:
  mock    — deterministic mock data for testing / demo
  adzuna  — real Adzuna API (requires ADZUNA_APP_ID + ADZUNA_APP_KEY)
  none/'' — disabled (no external jobs)
"""

import logging
import os
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# ── env config ────────────────────────────────────────────────────
_PROVIDER = os.environ.get("JOB_SOURCE_PROVIDER", "").strip().lower()
_API_KEY = os.environ.get("RAPIDAPI_KEY", "").strip()
_ADZUNA_APP_ID = os.environ.get("ADZUNA_APP_ID", "").strip()
_ADZUNA_APP_KEY = os.environ.get("ADZUNA_APP_KEY", "").strip()


def _get_provider():
    """Determine the active job-source provider at call time.

    If ``JOB_SOURCE_PROVIDER`` is explicitly set, honour it.
    Otherwise auto-detect: use Adzuna when its credentials are present.
    """
    explicit = os.environ.get("JOB_SOURCE_PROVIDER", "").strip().lower()
    if explicit and explicit != "none":
        return explicit
    # Auto-detect
    if (
        os.environ.get("ADZUNA_APP_ID", "").strip()
        and os.environ.get("ADZUNA_APP_KEY", "").strip()
    ):
        return "adzuna"
    return ""


def build_resume_query(skills, max_terms=5):
    """Build an API search query string from resume skills.

    Picks up to *max_terms* skills to form a concise query so the API
    returns relevant results for the user's background.
    """
    if not skills:
        return ""
    terms = [s for s in skills if s and s.lower() != "not detected"][:max_terms]
    return " ".join(terms)


def build_search_query(target_role, resume_text=""):
    """Build a simple, effective search query from target role + resume.

    Keeps the query concise — too many terms reduce API recall.
    Extracts at most 2 strong keywords from the resume text.
    """
    base_query = (target_role or "").strip()

    keywords = []
    if resume_text:
        text_lower = resume_text.lower()
        # Extract strong, common keywords from resume
        _STRONG_KEYWORDS = [
            "python",
            "sql",
            "java",
            "javascript",
            "react",
            "node.js",
            "aws",
            "docker",
            "kubernetes",
            "machine learning",
            "data",
            "typescript",
            "flask",
            "django",
            "excel",
            "tableau",
            "figma",
            "css",
            "html",
            "c++",
            "c#",
            "ruby",
            "go",
            "marketing",
            "sales",
            "finance",
            "analytics",
            "devops",
        ]
        for kw in _STRONG_KEYWORDS:
            if kw in text_lower:
                keywords.append(kw)
            if len(keywords) >= 2:
                break

    keyword_str = " ".join(keywords[:2])
    return f"{base_query} {keyword_str}".strip()


# ── M88 — Skill extraction ───────────────────────────────────────

SKILL_VOCABULARY = frozenset(
    [
        "a/b testing",
        "agile",
        "airflow",
        "analytics",
        "api",
        "aws",
        "azure",
        "c",
        "c#",
        "c++",
        "ci/cd",
        "communication",
        "compliance",
        "content strategy",
        "copywriting",
        "crm",
        "css",
        "customer success",
        "database administration",
        "design systems",
        "digital marketing",
        "django",
        "docker",
        "embedded",
        "etl",
        "excel",
        "facilitation",
        "figma",
        "financial modeling",
        "flask",
        "game design",
        "git",
        "graphql",
        "hr management",
        "html",
        "instructional design",
        "java",
        "javascript",
        "keyword research",
        "kubernetes",
        "linux",
        "machine learning",
        "monitoring",
        "networking",
        "node.js",
        "operations",
        "pandas",
        "power bi",
        "presentation",
        "product strategy",
        "program management",
        "project management",
        "prototyping",
        "python",
        "react",
        "react native",
        "recruiting",
        "reporting",
        "requirements analysis",
        "rest",
        "risk management",
        "roadmapping",
        "ruby",
        "salesforce",
        "scrum",
        "security",
        "selenium",
        "seo",
        "social media",
        "solidity",
        "sourcing",
        "spark",
        "sql",
        "stakeholder management",
        "statistics",
        "strategy",
        "tableau",
        "technical writing",
        "tensorflow",
        "terraform",
        "testing",
        "troubleshooting",
        "typescript",
        "unity",
        "user research",
        "video editing",
        "wireframing",
    ]
)

# Pre-sorted by length descending so multi-word skills match first
_SORTED_SKILLS = sorted(SKILL_VOCABULARY, key=len, reverse=True)


def extract_skills_from_text(text):
    """Extract known skills from free-form text (title + description).

    Uses the internal skill vocabulary.  Multi-word skills are matched
    first so e.g. "machine learning" is captured before "machine".
    Returns a deduplicated sorted list.
    """
    if not text:
        return []
    lower = text.lower()
    found = []
    for skill in _SORTED_SKILLS:
        if skill in lower:
            found.append(skill)
            # Remove matched phrase so sub-tokens don't double-match
            lower = lower.replace(skill, " ")
    return sorted(set(found))


# ── helpers ───────────────────────────────────────────────────────


def _normalize(raw, source_name):
    """Normalise a raw dict to the canonical external-job shape.

    Returns *None* if required fields are missing so callers can skip it.
    If the job has no explicit skills list, skills are extracted from
    the title + description text via M88 skill extraction.
    """
    title = (raw.get("title") or "").strip()
    company = (raw.get("company") or "").strip()
    if not title or not company:
        return None

    skills = list(raw.get("skills") or [])
    if not skills:
        # M88: extract skills from text for messy provider data
        text = f"{title} {raw.get('description', '')}"
        skills = extract_skills_from_text(text)

    return {
        "id": raw.get("id")
        or f"ext_{source_name}_{hash(title + company) & 0xFFFFFFFF:08x}",
        "source": "external",
        "source_name": source_name,
        "title": title,
        "company": company,
        "location": (raw.get("location") or "").strip(),
        "remote": bool(raw.get("remote")),
        "skills": skills,
        "description": (raw.get("description") or "").strip(),
        "posted_at": raw.get("posted_at") or None,
        "url": raw.get("url") or None,
        "apply_url": raw.get("apply_url") or raw.get("url") or None,
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
            "apply_url": "https://example.com/apply/react-dev",
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
            "apply_url": "https://example.com/apply/python-be",
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
            "apply_url": "https://example.com/apply/data-analyst",
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
            "apply_url": "https://example.com/apply/devops",
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
            "apply_url": "https://example.com/apply/marketing-mgr",
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
            j
            for j in results
            if q
            in " ".join(
                [
                    j.get("title", ""),
                    j.get("company", ""),
                    " ".join(j.get("skills", [])),
                ]
            ).lower()
        ]

    return results[:limit]


# ── Adzuna adapter (M87) ─────────────────────────────────────────

import urllib.request
import urllib.parse
import json as _json


def _adzuna_http_request(url, timeout=8):
    """Isolated HTTP call for easy testing / mocking."""
    req = urllib.request.Request(url, headers={"User-Agent": "Offerion/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return _json.loads(resp.read().decode())


def _fetch_adzuna(query=None, location=None, remote=None, limit=25):
    """Fetch jobs from the Adzuna API.

    Requires ``ADZUNA_APP_ID`` and ``ADZUNA_APP_KEY`` env vars.
    Returns raw dicts that ``_normalize`` will canonicalise.
    """
    app_id = os.environ.get("ADZUNA_APP_ID", "").strip()
    app_key = os.environ.get("ADZUNA_APP_KEY", "").strip()
    if not app_id or not app_key:
        logger.warning("Adzuna credentials missing — skipping provider")
        return []

    params = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": min(limit, 50),
        "content-type": "application/json",
    }
    if query:
        params["what"] = query
    if location:
        params["where"] = location

    url = "https://api.adzuna.com/v1/api/jobs/us/search/1?" + urllib.parse.urlencode(
        params
    )

    data = _adzuna_http_request(url)
    results = data.get("results", [])

    jobs = []
    for r in results:
        loc_name = ""
        loc_area = r.get("location", {}).get("area", [])
        if loc_area:
            loc_name = ", ".join(loc_area[-2:])  # city, state

        title_lower = (r.get("title") or "").lower()
        desc_lower = (r.get("description") or "").lower()
        is_remote = "remote" in title_lower or "remote" in desc_lower

        if remote is True and not is_remote:
            continue
        if remote is False and is_remote:
            continue

        jobs.append(
            {
                "id": f"adzuna_{r.get('id', '')}",
                "title": r.get("title", ""),
                "company": (r.get("company", {}) or {}).get("display_name", ""),
                "location": loc_name,
                "remote": is_remote,
                "description": r.get("description", ""),
                "posted_at": (r.get("created") or "")[:10],  # YYYY-MM-DD
                "url": r.get("redirect_url") or r.get("url") or "",
                "apply_url": r.get("redirect_url") or "",
            }
        )

    return jobs[:limit]


# ── provider registry ────────────────────────────────────────────

_PROVIDERS = {
    "mock": _fetch_mock,
    "adzuna": _fetch_adzuna,
}


# ── public API ────────────────────────────────────────────────────


def fetch_external_jobs(
    query=None,
    location=None,
    remote=None,
    limit=25,
    provider_override=None,
):
    """Return normalised jobs from configured external sources.

    Falls back to an empty list when no source is configured or the
    provider raises an exception.
    """
    provider = (provider_override or _get_provider() or "").strip().lower()
    if not provider or provider == "none":
        return []

    if provider not in _PROVIDERS:
        logger.warning("Unknown job source provider '%s' — returning empty", provider)
        return []

    adapter = _PROVIDERS[provider]
    try:
        raw_jobs = adapter(query=query, location=location, remote=remote, limit=limit)
    except Exception:
        logger.exception("External job source '%s' failed", provider)
        return []

    normalised = []
    for raw in raw_jobs:
        try:
            item = _normalize(raw, provider)
            if item:
                normalised.append(item)
        except Exception:
            logger.warning("Skipped malformed external job entry")
            continue

    return normalised[:limit]
