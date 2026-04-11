"""M70 — Job Matching Engine. Rank jobs by skill overlap with resume."""

from app.utils.job_data import get_all_jobs


def match_jobs(report_data, limit=5):
    """Return top *limit* jobs ranked by skill overlap with the resume.

    Each result contains: id, title, company, location, score, matched_skills.
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

    results = []
    for job in get_all_jobs():
        job_skills = {s.lower().strip() for s in job.get("skills", [])}
        if not job_skills:
            continue

        overlap = resume_skills & job_skills
        score = len(overlap) / len(job_skills)

        # Boost if job title contains the target role (or vice versa)
        if target_role:
            job_title_lower = job["title"].lower()
            if target_role in job_title_lower or job_title_lower in target_role:
                score = min(score + 0.1, 1.0)

        if score > 0:
            results.append(
                {
                    "id": job["id"],
                    "title": job["title"],
                    "company": job["company"],
                    "location": job.get("location", ""),
                    "score": round(score, 2),
                    "matched_skills": sorted(overlap),
                }
            )

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:limit]
