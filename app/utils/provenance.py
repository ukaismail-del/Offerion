"""M40 — Confidence + Data Provenance Layer.

Clarifies where Offerion's outputs came from and how certain they are.
"""


def build_provenance(session):
    """Build provenance metadata from current session state."""
    enhanced_resume = session.get("enhanced_resume")
    cover_letter_draft = session.get("cover_letter_draft")
    enhanced_cover_letter = session.get("enhanced_cover_letter")
    report_data = session.get("report_data")

    # Resume source
    if enhanced_resume:
        resume_source = "enhanced"
    elif report_data:
        resume_source = "structured"
    else:
        resume_source = "none"

    # Cover letter source
    if enhanced_cover_letter:
        cover_letter_source = "enhanced"
    elif cover_letter_draft:
        cover_letter_source = "draft"
    else:
        cover_letter_source = "none"

    # Intelligence source
    match_intelligence_source = "deterministic"

    # Confidence labels — based on data availability
    has_match = bool(report_data and report_data.get("match"))
    has_jd = bool(report_data and report_data.get("jd_comparison"))
    has_tailored = bool(report_data and report_data.get("tailored"))

    base_confidence = "Low"
    if has_match and has_tailored:
        base_confidence = "Moderate"
    if has_match and has_jd and has_tailored:
        base_confidence = "Strong"

    confidence_labels = {
        "match_explanation": base_confidence if has_match else "Low",
        "keyword_gaps": base_confidence if has_match else "Low",
        "priority_fixes": base_confidence if has_match else "Low",
        "role_fit_suggestions": base_confidence if has_match else "Low",
    }

    notes = _build_notes(resume_source, cover_letter_source, has_match, has_jd)

    return {
        "resume_source": resume_source,
        "cover_letter_source": cover_letter_source,
        "match_intelligence_source": match_intelligence_source,
        "confidence_labels": confidence_labels,
        "notes": notes,
    }


def _build_notes(resume_source, cl_source, has_match, has_jd):
    """Generate short provenance notes."""
    notes = []

    if resume_source == "enhanced":
        notes.append("Resume has been enhanced with role-targeted optimizations.")
    elif resume_source == "structured":
        notes.append(
            "Resume analysis is based on structured extraction from your uploaded file."
        )

    if cl_source == "enhanced":
        notes.append("Cover letter has been enhanced for tone and alignment.")
    elif cl_source == "draft":
        notes.append(
            "Cover letter is a generated draft — consider enhancing for best results."
        )

    if has_match and has_jd:
        notes.append(
            "Match intelligence uses both target role keywords and full job description."
        )
    elif has_match:
        notes.append("Match intelligence is based on target role keywords only.")

    notes.append(
        "Recommendations are based on structured resume and job-match signals."
    )
    notes.append("Outputs do not guarantee hiring outcomes.")

    return notes


SOURCE_LABELS = {
    "none": "Not available",
    "structured": "Structured extraction",
    "enhanced": "Enhanced",
    "draft": "Generated draft",
    "deterministic": "Rule-based analysis",
}


def get_source_label(source_key):
    """Return a readable label for a source key."""
    return SOURCE_LABELS.get(source_key, source_key)
