"""Deterministic resume enhancement layer.

Transforms structured analysis data into polished, resume-ready language
without fabricating employers, dates, or achievements.
"""

_STRONG_VERBS = [
    "Spearheaded",
    "Delivered",
    "Optimized",
    "Architected",
    "Implemented",
    "Streamlined",
    "Drove",
    "Managed",
    "Developed",
    "Led",
    "Built",
    "Designed",
    "Executed",
    "Improved",
    "Collaborated",
]


def enhance_resume(
    profile=None, tailored=None, rewrite=None, match=None, job_context=None
):
    """Build an enhanced resume object from analysis outputs.

    Returns a dict with polished summary, skills, experience bullets,
    education, and ATS notes. Returns None if insufficient data.
    When *job_context* is provided (M96), skills and summary are
    auto-targeted toward the selected job.
    """
    if not profile and not tailored:
        return None

    target_title = _resolve_target_title(tailored, match, job_context)
    name = _resolve_field(profile, "name")
    contact = _build_contact_line(profile)
    enhanced_summary = _build_summary(
        profile, tailored, rewrite, target_title, job_context
    )
    enhanced_skills = _build_skills(profile, tailored, job_context)
    enhanced_experience = _build_experience(tailored, rewrite)
    enhanced_education = _build_education(profile)
    ats_notes = _build_ats_notes(rewrite)

    # M107/M108: targeting metadata for UX clarity + explainability
    targeting = _build_targeting_metadata(job_context, enhanced_skills, profile)

    return {
        "name": name,
        "contact": contact,
        "target_title": target_title,
        "enhanced_summary": enhanced_summary,
        "enhanced_skills": enhanced_skills,
        "enhanced_experience_bullets": enhanced_experience,
        "enhanced_education": enhanced_education,
        "ats_alignment_notes": ats_notes,
        "targeting": targeting,
    }


def _resolve_target_title(tailored, match, job_context=None):
    if job_context and job_context.get("title"):
        return job_context["title"]
    if tailored and tailored.get("target_title"):
        return tailored["target_title"]
    if match and match.get("target_role"):
        return match["target_role"]
    return ""


def _resolve_field(profile, field):
    if not profile:
        return ""
    val = profile.get(field, "Not detected")
    return "" if val == "Not detected" else val


def _build_contact_line(profile):
    if not profile:
        return ""
    parts = []
    email = profile.get("email", "Not detected")
    phone = profile.get("phone", "Not detected")
    if email != "Not detected":
        parts.append(email)
    if phone != "Not detected":
        parts.append(phone)
    return " | ".join(parts)


def _build_summary(profile, tailored, rewrite, target_title, job_context=None):
    """Compose a polished 2-4 sentence professional summary."""
    fragments = []

    # Gather guidance
    if tailored and tailored.get("professional_summary"):
        fragments.extend(tailored["professional_summary"])
    elif rewrite and rewrite.get("summary_focus"):
        fragments.extend(rewrite["summary_focus"])

    # M96/M101: incorporate job-specific focus when available
    focus_areas_from_job = []
    domain_hint = None
    if job_context:
        gap = job_context.get("gap") or {}
        intel = job_context.get("intelligence") or {}
        focus_areas_from_job = gap.get("recommended_focus", [])
        domain_hint = intel.get("domain_hint")

    if not fragments:
        skills = profile.get("skills", []) if profile else []
        # M101: prefer matched skills, then required skills, then profile skills
        if job_context and job_context.get("matched_skills"):
            top = ", ".join(job_context["matched_skills"][:4])
        elif job_context and (job_context.get("intelligence") or {}).get(
            "required_skills"
        ):
            top = ", ".join(job_context["intelligence"]["required_skills"][:4])
        elif skills:
            top = ", ".join(skills[:4])
        else:
            top = "core competencies"
        if target_title and top:
            # M101: incorporate domain hint for stronger positioning
            domain_phrase = f" in the {domain_hint} space" if domain_hint else ""
            summary = (
                f"Results-driven professional with expertise in {top}, "
                f"seeking to leverage proven capabilities in a {target_title} role{domain_phrase}. "
                "Committed to delivering measurable outcomes and continuous improvement."
            )
            if focus_areas_from_job:
                summary += f" Key focus: {focus_areas_from_job[0]}."
            return summary
        return (
            "Dedicated professional with a strong track record of delivering results. "
            "Seeking to apply core competencies to drive impact in the target role."
        )

    # Convert guidance fragments into polished prose
    skills = profile.get("skills", []) if profile else []
    # M101: prefer matched/required skills for the top-skills mention
    if job_context and job_context.get("matched_skills"):
        top_skills = ", ".join(job_context["matched_skills"][:3])
    else:
        top_skills = ", ".join(skills[:3]) if skills else "core competencies"

    opening = (
        f"Results-driven {target_title} professional"
        if target_title
        else "Seasoned professional"
    )

    # Use first two guidance points as focus areas
    focus_areas = []
    for frag in fragments[:2]:
        cleaned = frag.strip().rstrip(".")
        # Lower-case the first letter if it starts with an upper imperative
        if cleaned and cleaned[0].isupper():
            cleaned = cleaned[0].lower() + cleaned[1:]
        focus_areas.append(cleaned)

    focus_text = (
        " and ".join(focus_areas) if focus_areas else "delivering measurable outcomes"
    )

    summary = (
        f"{opening} with demonstrated expertise in {top_skills}. "
        f"Proven ability to {focus_text}. "
        "Committed to continuous improvement and delivering high-impact results."
    )
    return summary


def _build_skills(profile, tailored, job_context=None):
    """Deduplicated, priority-ordered skill list."""
    skills = []
    seen = set()

    # M101: matched skills first (candidate already has these — highest relevance)
    if job_context and job_context.get("matched_skills"):
        for s in job_context["matched_skills"]:
            s = s.strip()
            if s and s.lower() not in seen:
                skills.append(s)
                seen.add(s.lower())

    # M96/M101: job-targeted required skills next
    if job_context and job_context.get("intelligence"):
        for s in job_context["intelligence"].get("required_skills") or []:
            s = s.strip()
            if s and s.lower() not in seen:
                skills.append(s)
                seen.add(s.lower())

    # Priority: tailored skills first
    if tailored and tailored.get("skills_to_feature"):
        for sf in tailored["skills_to_feature"]:
            s = sf.get("skill", "").strip()
            if s and s.lower() not in seen:
                skills.append(s)
                seen.add(s.lower())

    # Then missing keywords
    if tailored and tailored.get("priority_keywords"):
        for kw in tailored["priority_keywords"]:
            if kw.get("status") == "missing":
                s = kw["keyword"].strip()
                if s and s.lower() not in seen:
                    skills.append(s)
                    seen.add(s.lower())

    # Then profile skills
    if profile and profile.get("skills"):
        for s in profile["skills"]:
            s = s.strip()
            if s and s.lower() not in seen:
                skills.append(s)
                seen.add(s.lower())

    return skills[:12]


def _build_experience(tailored, rewrite):
    """Convert focus points and bullet guidance into action-oriented bullets."""
    bullets = []

    # Convert experience focus points into polished bullets
    if tailored and tailored.get("experience_focus_points"):
        for i, point in enumerate(tailored["experience_focus_points"][:4]):
            verb = _STRONG_VERBS[i % len(_STRONG_VERBS)]
            cleaned = point.strip().rstrip(".")
            # If already starts with a verb, use as-is but capitalize
            if cleaned and cleaned[0].isupper() and " " in cleaned:
                bullets.append(cleaned + ".")
            else:
                bullets.append(f"{verb} {cleaned}.")

    # Add bullet improvements as polished suggestions
    if rewrite and rewrite.get("bullet_improvements"):
        for item in rewrite["bullet_improvements"][:2]:
            cleaned = item.strip().rstrip(".")
            if cleaned:
                if cleaned[0].islower():
                    cleaned = cleaned[0].upper() + cleaned[1:]
                bullets.append(cleaned + ".")

    if not bullets:
        bullets = [
            "Led cross-functional initiatives to deliver projects on time and within scope.",
            "Improved processes and workflows to drive measurable efficiency gains.",
            "Collaborated with stakeholders to align deliverables with business objectives.",
        ]

    return bullets[:6]


def _build_education(profile):
    if profile and profile.get("education"):
        return list(profile["education"])
    return []


def _build_ats_notes(rewrite):
    notes = []
    if not rewrite:
        return notes
    if rewrite.get("ats_notes"):
        notes.extend(rewrite["ats_notes"])
    if rewrite.get("keyword_additions"):
        kws = ", ".join(rewrite["keyword_additions"][:5])
        notes.append(f"Consider weaving in: {kws}")
    return notes


# ------------------------------------------------------------------
# M107/M108 — Targeting metadata
# ------------------------------------------------------------------


def _build_targeting_metadata(job_context, enhanced_skills, profile):
    """Return a compact dict describing what influenced the enhancement.

    Keys:
        mode       – "job-targeted" | "generic"
        job_title  – the job title used, or None
        company    – the company used, or None
        matched    – skills the candidate already has that matched the job
        emphasized – focus areas that were prioritised
        omitted    – missing skills NOT inserted (user should review)
    """
    if not job_context:
        return {
            "mode": "generic",
            "job_title": None,
            "company": None,
            "matched": [],
            "emphasized": [],
            "omitted": [],
        }

    matched = job_context.get("matched_skills") or []
    gap = job_context.get("gap") or {}
    intel = job_context.get("intelligence") or {}
    missing = gap.get("missing_skills") or intel.get("preferred_skills") or []
    focus = gap.get("recommended_focus") or []

    # Skills that were in the job but NOT inserted into the resume
    enhanced_lower = {s.lower() for s in (enhanced_skills or [])}
    omitted = [s for s in missing if s.lower() not in enhanced_lower]

    return {
        "mode": "job-targeted",
        "job_title": job_context.get("title"),
        "company": job_context.get("company"),
        "matched": list(matched[:8]),
        "emphasized": list(focus[:4]),
        "omitted": list(omitted[:6]),
    }
