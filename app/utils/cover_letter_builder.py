"""M26 — Cover Letter Draft Generator.

Builds a structured cover letter draft from session data.
Deterministic — no AI APIs, no fabrication.
"""


def build_cover_letter(profile=None, tailored=None, rewrite=None, match=None,
                       enhanced_resume=None):
    """Generate a structured cover letter draft.

    Returns a dict with recipient, company, target_title, opening,
    body_points, closing, and full_text.  Returns None when there is
    not enough data.
    """
    if not profile:
        return None

    target_title = _resolve_target_title(tailored, match, enhanced_resume)
    company = _resolve_company(match)
    recipient = "Hiring Team"
    name = _resolve_name(profile, enhanced_resume)

    # --- Opening paragraph ---
    opening = _build_opening(name, target_title, company)

    # --- Body points ---
    body_points = _build_body(profile, tailored, rewrite, match, enhanced_resume)

    # --- Closing paragraph ---
    closing = _build_closing(name, target_title)

    # --- Full text assembly ---
    full_text = _assemble(recipient, company, opening, body_points, closing, name)

    return {
        "recipient": recipient,
        "company": company,
        "target_title": target_title,
        "opening": opening,
        "body_points": body_points,
        "closing": closing,
        "full_text": full_text,
    }


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _resolve_target_title(tailored, match, enhanced_resume):
    if enhanced_resume and enhanced_resume.get("target_title"):
        return enhanced_resume["target_title"]
    if tailored and tailored.get("target_title"):
        return tailored["target_title"]
    if match and match.get("target_role"):
        return match["target_role"]
    return "the advertised position"


def _resolve_company(match):
    if match and match.get("company"):
        return match["company"]
    return "your organization"


def _resolve_name(profile, enhanced_resume):
    if enhanced_resume and enhanced_resume.get("name"):
        return enhanced_resume["name"]
    if profile and profile.get("name") and profile["name"] != "Not detected":
        return profile["name"]
    return "[Your Name]"


def _build_opening(name, target_title, company):
    return (
        f"I am writing to express my interest in the {target_title} "
        f"position at {company}. With a background that aligns closely "
        f"with the requirements of this role, I am confident in my ability "
        f"to contribute meaningfully to your team."
    )


def _build_body(profile, tailored, rewrite, match, enhanced_resume):
    points = []

    # Skills alignment
    skills = _gather_skills(profile, tailored, enhanced_resume)
    if skills:
        top = skills[:6]
        points.append(
            f"My core competencies include {', '.join(top)}, which directly "
            f"support the key requirements of this role."
        )

    # Experience focus
    exp = _gather_experience(tailored, enhanced_resume)
    if exp:
        points.append(
            "In my professional experience, I have focused on areas such as "
            + "; ".join(exp[:3]) + "."
        )

    # Match strengths
    if match and match.get("matched_keywords"):
        kws = match["matched_keywords"][:5]
        points.append(
            f"My profile demonstrates alignment with key target areas "
            f"including {', '.join(kws)}."
        )

    # Rewrite / keyword additions
    if rewrite and rewrite.get("keyword_additions"):
        adds = rewrite["keyword_additions"][:4]
        points.append(
            f"I am also actively strengthening my expertise in "
            f"{', '.join(adds)} to further align with your team's needs."
        )

    if not points:
        points.append(
            "My professional background and skill set position me well "
            "for this opportunity, and I look forward to discussing how "
            "I can contribute to your team."
        )

    return points


def _build_closing(name, target_title):
    return (
        f"I would welcome the opportunity to discuss how my background "
        f"and skills align with the {target_title} role. Thank you for "
        f"considering my application. I look forward to hearing from you."
    )


def _gather_skills(profile, tailored, enhanced_resume):
    if enhanced_resume and enhanced_resume.get("enhanced_skills"):
        return enhanced_resume["enhanced_skills"]
    if tailored and tailored.get("skills_to_feature"):
        return [s["skill"] for s in tailored["skills_to_feature"]]
    if profile and profile.get("skills"):
        return profile["skills"]
    return []


def _gather_experience(tailored, enhanced_resume):
    if enhanced_resume and enhanced_resume.get("enhanced_experience_bullets"):
        return enhanced_resume["enhanced_experience_bullets"]
    if tailored and tailored.get("experience_focus_points"):
        return tailored["experience_focus_points"]
    return []


def _assemble(recipient, company, opening, body_points, closing, name):
    lines = []
    lines.append(f"Dear {recipient},")
    lines.append("")
    lines.append(opening)
    lines.append("")
    for pt in body_points:
        lines.append(pt)
        lines.append("")
    lines.append(closing)
    lines.append("")
    lines.append("Sincerely,")
    lines.append(name)
    return "\n".join(lines)
