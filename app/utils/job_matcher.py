"""M76 — Advanced Job Matching Engine.

Weighted scoring: skill overlap (0.6) + title similarity (0.3) + experience signal (0.1).
Returns match_level and missing_skills alongside the score.
"""


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
        Pre-filtered job list (from job_feed.fetch_jobs).  Falls back to
        the full dataset when *None*.
    limit : int
        Maximum results to return.

    Returns
    -------
    list[dict]
        Each item: id, title, company, location, remote, score,
        match_level, matched_skills, missing_skills.
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

        score = (skill_score * 0.6) + (title_score * 0.3) + (exp_sig * 0.1)
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
                }
            )

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:limit]
