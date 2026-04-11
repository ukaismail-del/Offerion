"""M94 — Resume-to-Job Gap Analyzer.

Compares the active resume/profile against a selected job to produce
a structured fit assessment.  Deterministic — no external APIs.
"""

from app.utils.job_intelligence import extract_job_intelligence


def analyze_job_gap(report_data, job):
    """Compare active resume/profile against a selected job.

    Parameters
    ----------
    report_data : dict
        Session ``report_data`` containing ``profile`` and ``match`` keys.
    job : dict
        The target job dict (from dataset or unified feed).

    Returns
    -------
    dict with keys: fit_score, fit_level, matched_skills, missing_skills,
    resume_strengths, resume_gaps, recommended_focus.
    """
    if not report_data or not job:
        return _empty_result()

    profile = report_data.get("profile") or {}
    match_data = report_data.get("match") or {}

    # ── gather resume skills ──────────────────────────────────────
    resume_skills = set()
    if profile.get("skills"):
        resume_skills = {s.lower().strip() for s in profile["skills"]}

    # ── extract job intelligence ──────────────────────────────────
    intel = extract_job_intelligence(job)
    job_skills = {s.lower().strip() for s in job.get("skills", [])}
    # Also include extracted keywords we discovered
    job_skills |= {s.lower().strip() for s in intel.get("keywords", [])}

    if not job_skills:
        return _empty_result()

    # ── skill comparison ──────────────────────────────────────────
    matched = sorted(resume_skills & job_skills)
    missing = sorted(job_skills - resume_skills)

    fit_score = round(len(matched) / len(job_skills), 2) if job_skills else 0.0

    # ── fit level ─────────────────────────────────────────────────
    if fit_score >= 0.65:
        fit_level = "Strong"
    elif fit_score >= 0.35:
        fit_level = "Moderate"
    else:
        fit_level = "Weak"

    # ── resume strengths ──────────────────────────────────────────
    strengths = _identify_strengths(profile, match_data, matched, intel)

    # ── resume gaps ───────────────────────────────────────────────
    gaps = _identify_gaps(missing, intel)

    # ── recommended focus ─────────────────────────────────────────
    focus = _build_recommended_focus(intel, matched, missing, profile)

    return {
        "fit_score": fit_score,
        "fit_level": fit_level,
        "matched_skills": matched,
        "missing_skills": missing,
        "resume_strengths": strengths,
        "resume_gaps": gaps,
        "recommended_focus": focus,
    }


def _empty_result():
    return {
        "fit_score": 0.0,
        "fit_level": "Weak",
        "matched_skills": [],
        "missing_skills": [],
        "resume_strengths": [],
        "resume_gaps": [],
        "recommended_focus": [],
    }


def _identify_strengths(profile, match_data, matched, intel):
    """Build a list of concrete resume strengths relative to this job."""
    strengths = []

    if matched:
        top = matched[:5]
        strengths.append(f"Strong alignment in: {', '.join(top)}")

    # Experience depth
    experience = profile.get("experience", [])
    if len(experience) >= 4:
        strengths.append("Substantial professional experience demonstrated")
    elif len(experience) >= 2:
        strengths.append("Relevant professional experience demonstrated")

    # Seniority alignment
    seniority = intel.get("seniority_hint")
    if seniority and len(experience) >= 3:
        strengths.append(f"Experience depth aligns with {seniority}-level role")

    # Domain alignment
    domain = intel.get("domain_hint")
    target_role = (match_data.get("target_role") or "").lower()
    if domain and domain.lower() in target_role:
        strengths.append(f"Target role aligns with {domain} domain")

    return strengths[:5]


def _identify_gaps(missing, intel):
    """Build a list of concrete resume gaps for this job."""
    gaps = []

    required = set(intel.get("required_skills", []))
    missing_required = sorted(set(missing) & required)
    missing_preferred = sorted(set(missing) - required)

    if missing_required:
        gaps.append(f"Missing required skills: {', '.join(missing_required[:5])}")

    if missing_preferred:
        gaps.append(f"Missing preferred skills: {', '.join(missing_preferred[:4])}")

    seniority = intel.get("seniority_hint")
    if seniority and seniority in ("Senior", "Lead", "Principal", "Staff", "Director"):
        gaps.append(
            f"Role expects {seniority}-level depth — ensure experience reflects this"
        )

    return gaps[:4]


def _build_recommended_focus(intel, matched, missing, profile):
    """Identify what the candidate should emphasize in their application."""
    focus = []

    domain = intel.get("domain_hint")
    responsibilities = intel.get("responsibility_signals", [])

    # Map responsibilities to focus areas
    focus_map = {
        "build and maintain": "system design and reliability",
        "design and implement": "technical architecture",
        "collaborate with": "cross-team collaboration",
        "lead a team": "leadership and team management",
        "manage a team": "leadership and team management",
        "own the": "end-to-end ownership",
        "drive": "initiative and impact",
        "mentor": "mentorship and growth",
        "optimize": "performance optimization",
        "architect": "system architecture",
        "scale": "scalability and growth",
        "automate": "automation and efficiency",
        "analyze": "data analysis and insights",
        "present to stakeholders": "stakeholder communication",
        "manage stakeholders": "stakeholder management",
        "cross-functional": "cross-functional collaboration",
    }

    for resp in responsibilities[:3]:
        mapped = focus_map.get(resp)
        if mapped and mapped not in focus:
            focus.append(mapped)

    # Emphasize matched strengths
    if matched:
        focus.append(f"Highlight proficiency in {', '.join(matched[:3])}")

    # Address top missing skill
    if missing:
        focus.append(
            f"Address gap in {', '.join(missing[:2])} (show willingness to learn)"
        )

    # Domain-specific focus
    if domain:
        focus.append(f"Emphasize {domain} experience")

    return focus[:5]
