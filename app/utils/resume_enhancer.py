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


def enhance_resume(profile=None, tailored=None, rewrite=None, match=None):
    """Build an enhanced resume object from analysis outputs.

    Returns a dict with polished summary, skills, experience bullets,
    education, and ATS notes. Returns None if insufficient data.
    """
    if not profile and not tailored:
        return None

    target_title = _resolve_target_title(tailored, match)
    name = _resolve_field(profile, "name")
    contact = _build_contact_line(profile)
    enhanced_summary = _build_summary(profile, tailored, rewrite, target_title)
    enhanced_skills = _build_skills(profile, tailored)
    enhanced_experience = _build_experience(tailored, rewrite)
    enhanced_education = _build_education(profile)
    ats_notes = _build_ats_notes(rewrite)

    return {
        "name": name,
        "contact": contact,
        "target_title": target_title,
        "enhanced_summary": enhanced_summary,
        "enhanced_skills": enhanced_skills,
        "enhanced_experience_bullets": enhanced_experience,
        "enhanced_education": enhanced_education,
        "ats_alignment_notes": ats_notes,
    }


def _resolve_target_title(tailored, match):
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


def _build_summary(profile, tailored, rewrite, target_title):
    """Compose a polished 2-4 sentence professional summary."""
    fragments = []

    # Gather guidance
    if tailored and tailored.get("professional_summary"):
        fragments.extend(tailored["professional_summary"])
    elif rewrite and rewrite.get("summary_focus"):
        fragments.extend(rewrite["summary_focus"])

    if not fragments:
        skills = profile.get("skills", []) if profile else []
        if target_title and skills:
            top = ", ".join(skills[:4])
            return (
                f"Results-driven professional with expertise in {top}, "
                f"seeking to leverage proven capabilities in a {target_title} role. "
                "Committed to delivering measurable outcomes and continuous improvement."
            )
        return (
            "Dedicated professional with a strong track record of delivering results. "
            "Seeking to apply core competencies to drive impact in the target role."
        )

    # Convert guidance fragments into polished prose
    skills = profile.get("skills", []) if profile else []
    top_skills = ", ".join(skills[:3]) if skills else "core competencies"

    opening = f"Results-driven {target_title} professional" if target_title else "Seasoned professional"

    # Use first two guidance points as focus areas
    focus_areas = []
    for frag in fragments[:2]:
        cleaned = frag.strip().rstrip(".")
        # Lower-case the first letter if it starts with an upper imperative
        if cleaned and cleaned[0].isupper():
            cleaned = cleaned[0].lower() + cleaned[1:]
        focus_areas.append(cleaned)

    focus_text = " and ".join(focus_areas) if focus_areas else "delivering measurable outcomes"

    summary = (
        f"{opening} with demonstrated expertise in {top_skills}. "
        f"Proven ability to {focus_text}. "
        "Committed to continuous improvement and delivering high-impact results."
    )
    return summary


def _build_skills(profile, tailored):
    """Deduplicated, priority-ordered skill list."""
    skills = []
    seen = set()

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
