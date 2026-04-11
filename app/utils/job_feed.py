"""M75 — Job Feed Abstraction Layer.

Provides a single entry-point for fetching jobs with optional filters.
Currently backed by the static dataset; designed so an external API
source can be swapped in later without changing callers.
"""

from app.utils.job_data import get_all_jobs


def fetch_jobs(query=None, location=None, remote=None, limit=25):
    """Return jobs matching the given filters.

    Parameters
    ----------
    query : str | None
        Free-text search matched against job title, company, and skills.
    location : str | None
        Substring match on the job's location field.
    remote : bool | None
        If True, only remote jobs. If False, only on-site. None = all.
    limit : int
        Maximum results to return.

    Returns
    -------
    list[dict]
        Filtered list of job dicts (same shape as job_data entries).
    """
    jobs = get_all_jobs()

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

    return jobs[:limit]
