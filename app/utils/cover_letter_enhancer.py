"""M27 — Cover Letter Enhancement Layer.

Transforms a structured cover letter draft into stronger, more
professional application-ready language.  Deterministic — no AI APIs.
"""

_POWER_PHRASES = [
    "consistently delivered",
    "strategically contributed to",
    "demonstrated measurable impact in",
    "proactively advanced",
    "effectively collaborated on",
]


def enhance_cover_letter(cover_letter_draft, enhanced_resume=None, job_context=None):
    """Enhance a cover letter draft into polished prose.

    Returns a dict with recipient, company, target_title,
    enhanced_opening, enhanced_body, enhanced_closing, and full_text.
    Returns None if no draft is provided.

    When *job_context* is provided (M102), the opening and body are
    strengthened with domain/seniority specifics.
    """
    if not cover_letter_draft:
        return None

    target_title = cover_letter_draft.get("target_title", "the advertised position")
    company = cover_letter_draft.get("company", "your organization")
    recipient = cover_letter_draft.get("recipient", "Hiring Team")
    name = _resolve_name(cover_letter_draft, enhanced_resume)

    enhanced_opening = _enhance_opening(target_title, company, job_context)
    enhanced_body = _enhance_body(
        cover_letter_draft.get("body_points", []), target_title
    )
    enhanced_closing = _enhance_closing(target_title)

    full_text = _assemble(
        recipient, enhanced_opening, enhanced_body, enhanced_closing, name
    )

    return {
        "recipient": recipient,
        "company": company,
        "target_title": target_title,
        "enhanced_opening": enhanced_opening,
        "enhanced_body": enhanced_body,
        "enhanced_closing": enhanced_closing,
        "full_text": full_text,
    }


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def _resolve_name(draft, enhanced_resume):
    if enhanced_resume and enhanced_resume.get("name"):
        return enhanced_resume["name"]
    return "[Your Name]"


def _enhance_opening(target_title, company, job_context=None):
    # M102: incorporate domain/seniority when available
    domain_phrase = ""
    if job_context:
        intel = job_context.get("intelligence") or {}
        domain = intel.get("domain_hint")
        if domain:
            domain_phrase = f" in {domain}"

    return (
        f"I am excited to apply for the {target_title} position at {company}. "
        f"My professional background{domain_phrase} and proven skill set make me a strong "
        f"candidate for this role, and I am eager to bring my expertise to "
        f"your team."
    )


def _enhance_body(body_points, target_title):
    enhanced = []
    for i, point in enumerate(body_points):
        phrase = _POWER_PHRASES[i % len(_POWER_PHRASES)]
        # Strengthen the point while keeping original meaning
        cleaned = point.rstrip(".")
        if cleaned.lower().startswith("my "):
            # Keep first-person framing but strengthen
            enhanced.append(f"{cleaned}, and I have {phrase} results in this area.")
        elif cleaned.lower().startswith("i "):
            enhanced.append(
                f"{cleaned}. Throughout my career, I have {phrase} meaningful outcomes."
            )
        else:
            enhanced.append(
                f"{cleaned}. I have {phrase} tangible results aligned with this objective."
            )
        if len(enhanced) >= 5:
            break
    return enhanced


def _enhance_closing(target_title):
    return (
        f"I am enthusiastic about the opportunity to contribute to your "
        f"team in the {target_title} capacity. I welcome the chance to "
        f"discuss how my qualifications and professional experience can "
        f"support your goals. Thank you for your time and consideration."
    )


def _assemble(recipient, opening, body, closing, name):
    lines = []
    lines.append(f"Dear {recipient},")
    lines.append("")
    lines.append(opening)
    lines.append("")
    for pt in body:
        lines.append(pt)
        lines.append("")
    lines.append(closing)
    lines.append("")
    lines.append("Sincerely,")
    lines.append(name)
    return "\n".join(lines)
