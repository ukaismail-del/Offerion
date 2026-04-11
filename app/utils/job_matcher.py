"""M76/M83 — Advanced Job Matching Engine.

Weighted scoring:
  skill overlap (0.5) + title similarity (0.25) +
  experience signal (0.1) + freshness signal (0.15).

Returns match_level, missing_skills, freshness_score, and posted_at.
"""

from datetime import datetime, timedelta, timezone


def _title_similarity(target_role, job_title):
    """Token-overlap similarity between target role and job title (0-1)."""
    if not target_role:
        return 0.0
    a_tokens = set(target_role.lower().split())
    b_tokens = set(job_title.lower().split())
    if not a_tokens or not b_tokens:
        return 0.0
    overlap = a_tokens & b_tokens
    return len(overlap) / max(len(a_tokens), len(b_tokens))


def _experience_signal(profile):
    """Quick proxy for experience depth (0-1).

    Uses the length of the detected experience lines list (max 6 entries
    from resume_analyzer).  More lines ≈ more experience.
    """
    exp_lines = profile.get("experience", []) if profile else []
    return min(len(exp_lines) / 6.0, 1.0)


def _freshness_signal(posted_at):
    """Score 0-1 based on how recently a job was posted.

    * Today            → 1.0
    * 3 days ago       → ~0.8
    * 7 days ago       → ~0.5
    * 30+ days ago     → ~0.05
    * Missing date     → 0.5 (neutral)
    """
    if not posted_at:
        return 0.5  # neutral when date unknown

    try:
        posted = datetime.strptime(str(posted_at)[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return 0.5

    days_old = max((datetime.now(timezone.utc).replace(tzinfo=None) - posted).days, 0)
    if days_old == 0:
        return 1.0
    # Exponential decay: half-life ≈ 7 days
    return max(round(2 ** (-days_old / 7.0), 3), 0.02)


def _match_level(score):
    if score >= 0.65:
        return "Strong"
    if score >= 0.35:
        return "Moderate"
    return "Weak"


def match_jobs(report_data, jobs=None, limit=10):
    """Return top *limit* jobs ranked by weighted match score.

    Parameters
    ----------
    report_data : dict
        Session report_data containing ``profile`` and ``match`` keys.
    jobs : list[dict] | None
        Pre-filtered job list (from job_feed).  Falls back to
        the full dataset when *None*.
    limit : int
        Maximum results to return.

    Returns
    -------
    list[dict]
        Each item: id, title, company, location, remote, score,
        match_level, matched_skills, missing_skills,
        freshness_score, posted_at, source, source_name, url.
    """
    if not report_data:
        return []

    profile = report_data.get("profile")
    match_data = report_data.get("match")

    resume_skills = set()
    if profile and profile.get("skills"):
        resume_skills = {s.lower().strip() for s in profile["skills"]}

    target_role = ""
    if match_data and match_data.get("target_role"):
        target_role = match_data["target_role"].lower().strip()

    if not resume_skills:
        return []

    if jobs is None:
        from app.utils.job_data import get_all_jobs

        jobs = get_all_jobs()

    exp_sig = _experience_signal(profile)

    results = []
    for job in jobs:
        job_skills = {s.lower().strip() for s in job.get("skills", [])}
        if not job_skills:
            continue

        overlap = resume_skills & job_skills
        skill_score = len(overlap) / len(job_skills)
        title_score = _title_similarity(target_role, job["title"])
        fresh = _freshness_signal(job.get("posted_at"))

        score = (
            (skill_score * 0.5)
            + (title_score * 0.25)
            + (exp_sig * 0.1)
            + (fresh * 0.15)
        )
        score = min(round(score, 2), 1.0)

        if score > 0:
            missing = job_skills - resume_skills
            results.append(
                {
                    "id": job["id"],
                    "title": job["title"],
                    "company": job["company"],
                    "location": job.get("location", ""),
                    "remote": job.get("remote", False),
                    "score": score,
                    "match_level": _match_level(score),
                    "matched_skills": sorted(overlap),
                    "missing_skills": sorted(missing),
                    "freshness_score": round(fresh, 3),
                    "posted_at": job.get("posted_at"),
                    "source": job.get("source", "internal"),
                    "source_name": job.get("source_name"),
                    "url": job.get("url"),
                    "apply_url": job.get("apply_url"),
                }
            )

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:limit]
