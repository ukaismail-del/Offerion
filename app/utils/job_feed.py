"""M75/M82/Z — Job Feed Abstraction Layer.

Provides a single entry-point for fetching jobs with optional filters.
``get_unified_jobs`` merges internal + external sources with deduplication.
When resume skills are provided the API query is derived automatically
so different resumes produce different job results.
"""

import logging
import os

from app.utils.job_data import get_all_jobs, get_static_jobs
from app.utils.job_sources import (
    fetch_external_jobs,
    build_resume_query,
    build_search_query,
)

logger = logging.getLogger(__name__)


_FALLBACK_QUERIES = [
    "software engineer",
    "developer",
    "engineer",
    "analyst",
]


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
    query=None,
    location=None,
    remote=None,
    source=None,
    limit=25,
    resume_skills=None,
    target_role=None,
    resume_text=None,
    ensure_results=False,
):
    """Merge internal dataset + external jobs, deduplicate, filter, return.

    When *resume_skills* are provided and no explicit *query*, a search
    query is built from the user's skills so the API returns
    personalised results — different resumes yield different jobs.

    **Fallback**: if the primary query returns zero external jobs, the
    function retries with progressively broader queries so the user
    always sees results.  ``used_fallback`` is set on the returned list
    as an attribute when a fallback query was used.

    When duplicates exist (same title+company+location), the external
    version is preferred because it typically has richer metadata
    (posted_at, url, source_name).
    """
    # ── Build smart query ────────────────────────────────────────
    api_query = query
    query_source = "manual"
    if not api_query and target_role:
        api_query = build_search_query(target_role, resume_text or "")
        query_source = "target_role"
    if not api_query and resume_skills:
        api_query = build_resume_query(resume_skills)
        query_source = "resume_skills"
    if not api_query:
        query_source = "broad"

    logger.info("Job feed query: %s", api_query or "(none)")

    # ── Fetch internal ───────────────────────────────────────────
    internal = get_all_jobs()

    # ── Fetch external with fallback ─────────────────────────────
    external = []
    used_fallback = False
    fallback_query_used = None
    fallback_stage = "none"
    supply_notice = None
    live_source_status = "ok"
    used_static_fallback = False
    used_mock_fallback = False
    fetch_limit = max(limit, 50)

    # Clean location — avoid sending empty strings
    clean_location = (location or "").strip() or None

    try:
        external = fetch_external_jobs(
            query=api_query or None,
            location=clean_location,
            remote=remote,
            limit=fetch_limit,
        )
    except Exception:
        logger.exception("External job source failed on primary query")
        live_source_status = "unavailable"

    if not external:
        explicit_provider = os.environ.get("JOB_SOURCE_PROVIDER", "").strip().lower()
        has_adzuna = bool(
            os.environ.get("ADZUNA_APP_ID", "").strip()
            and os.environ.get("ADZUNA_APP_KEY", "").strip()
        )
        if explicit_provider in ("", "none") and not has_adzuna:
            live_source_status = "unavailable"

    logger.info("Primary query returned %d external jobs", len(external))

    # Fallback cascade when primary returns nothing
    # Skip fallback when the caller supplied an explicit query — respect it.
    if not external and not query:
        fallback_attempts = []
        if target_role:
            fallback_attempts.append(target_role.strip())
        fallback_attempts.extend(_FALLBACK_QUERIES)

        for fq in fallback_attempts:
            if fq == api_query:
                continue  # skip if same as primary
            try:
                logger.info("Fallback query: %s", fq)
                external = fetch_external_jobs(
                    query=fq,
                    location=clean_location,
                    remote=remote,
                    limit=fetch_limit,
                )
            except Exception:
                logger.exception("Fallback query '%s' failed", fq)
                continue
            if external:
                used_fallback = True
                fallback_query_used = fq
                fallback_stage = "query"
                logger.info("Fallback '%s' returned %d jobs", fq, len(external))
                break

    # Optional mock fallback stage (Bundle Z reliability)
    allow_mock_fallback = os.environ.get(
        "JOB_SOURCE_ENABLE_MOCK_FALLBACK", ""
    ).strip().lower() in ("1", "true", "yes")
    if not external and allow_mock_fallback:
        try:
            mock_jobs = fetch_external_jobs(
                query=api_query or None,
                location=clean_location,
                remote=remote,
                limit=fetch_limit,
                provider_override="mock",
            )
            if mock_jobs:
                external = mock_jobs
                used_fallback = True
                used_mock_fallback = True
                fallback_stage = "mock"
        except Exception:
            logger.exception("Mock fallback query failed")

    logger.info("Total external jobs: %d (fallback=%s)", len(external), used_fallback)

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

    # Final safety fallback for core product flow.
    # Trigger only when caller opts in and there are no merged jobs at all.
    if ensure_results and not merged:
        static_fallback = get_static_jobs()
        if static_fallback:
            for j in static_fallback:
                j.setdefault("source", "internal")
                j.setdefault("posted_at", None)
                j.setdefault("url", None)
            merged = list(static_fallback)
            used_fallback = True
            used_static_fallback = True
            fallback_stage = "static"
            supply_notice = "fallback_static"

    # Apply filters on the merged list
    merged = _apply_filters(merged, query=query, location=location, remote=remote)

    result = merged[:limit]

    # Attach fallback flag so callers can show a banner
    result = _TaggedList(result)
    result.used_fallback = used_fallback
    result.primary_query = api_query
    result.fallback_query = fallback_query_used
    result.query_source = query_source
    result.fallback_stage = fallback_stage
    result.used_mock_fallback = used_mock_fallback
    result.used_static_fallback = used_static_fallback
    result.live_source_status = live_source_status
    result.supply_notice = supply_notice
    return result


class _TaggedList(list):
    """List subclass that carries metadata attributes."""

    used_fallback = False


def fetch_jobs(query=None, location=None, remote=None, limit=25):
    """Filter internal jobs only (legacy helper, still used by some callers)."""
    jobs = get_all_jobs()
    jobs = _apply_filters(jobs, query=query, location=location, remote=remote)
    return jobs[:limit]
