"""M75/M82 — Job Feed Abstraction Layer.

Provides a single entry-point for fetching jobs with optional filters.
``get_unified_jobs`` merges internal + external sources with deduplication.
When resume skills are provided the API query is derived automatically
so different resumes produce different job results.
"""

import logging

from app.utils.job_data import get_all_jobs
from app.utils.job_sources import fetch_external_jobs, build_resume_query

logger = logging.getLogger(__name__)


def _apply_filters(jobs, query=None, location=None, remote=None):
    """Apply query/location/remote filters to a job list."""
    if remote is not None:
        jobs = [j for j in jobs if j.get("remote") is remote]

    if location:
        loc_lower = location.lower().strip()
        jobs = [j for j in jobs if loc_lower in j.get("location", "").lower()]

    if query:
        q = query.lower().strip()
        filtered = []
        for j in jobs:
            haystack = " ".join(
                [
                    j.get("title", ""),
                    j.get("company", ""),
                    " ".join(j.get("skills", [])),
                ]
            ).lower()
            if q in haystack:
                filtered.append(j)
        jobs = filtered

    return jobs


def _dedup_key(job):
    """Normalised deduplication key: (title, company, location)."""
    return (
        job.get("title", "").lower().strip(),
        job.get("company", "").lower().strip(),
        job.get("location", "").lower().strip(),
    )


def get_unified_jobs(
    query=None, location=None, remote=None, source=None, limit=25, resume_skills=None
):
    """Merge internal dataset + external jobs, deduplicate, filter, return.

    When *resume_skills* are provided and no explicit *query*, a search
    query is built from the user's skills so the API returns
    personalised results — different resumes yield different jobs.

    When duplicates exist (same title+company+location), the external
    version is preferred because it typically has richer metadata
    (posted_at, url, source_name).
    """
    # Derive API query from resume skills when no explicit query given
    api_query = query
    if not api_query and resume_skills:
        api_query = build_resume_query(resume_skills)

    # Fetch from both sources
    internal = get_all_jobs()
    try:
        external = fetch_external_jobs(
            query=api_query or None,
            location=location,
            remote=remote,
            limit=max(limit, 50),  # fetch extra for scoring diversity
        )
    except Exception:
        logger.exception("External job fetch failed; using internal only")
        external = []

    # Tag internal jobs with source if not already present
    for j in internal:
        j.setdefault("source", "internal")
        j.setdefault("posted_at", None)
        j.setdefault("url", None)

    # Build deduplicated dict — external wins on collision
    seen = {}
    for j in internal:
        seen[_dedup_key(j)] = j
    for j in external:
        seen[_dedup_key(j)] = j  # overwrites internal duplicate

    merged = list(seen.values())

    # M91: source filter
    if source == "internal":
        merged = [j for j in merged if j.get("source") == "internal"]
    elif source == "external":
        merged = [j for j in merged if j.get("source") == "external"]

    # Apply filters on the merged list
    merged = _apply_filters(merged, query=query, location=location, remote=remote)

    return merged[:limit]


def fetch_jobs(query=None, location=None, remote=None, limit=25):
    """Filter internal jobs only (legacy helper, still used by some callers)."""
    jobs = get_all_jobs()
    jobs = _apply_filters(jobs, query=query, location=location, remote=remote)
    return jobs[:limit]
