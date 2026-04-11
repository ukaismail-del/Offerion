def generate_rewrite_guidance(resume_text, profile, match=None, jd_comparison=None):
    """Generate ATS rewrite guidance based on profile, match, and JD comparison.

    Returns a dict with summary_focus, keyword_additions, bullet_improvements,
    section_improvements, and ats_notes. Returns None if there is not enough
    analysis context to produce useful guidance.
    """
    has_match = match is not None
    has_jd = jd_comparison is not None

    # Need at least a profile to generate guidance
    if not profile:
        return None

    skills = [s for s in profile.get("skills", []) if s != "Not detected"]
    edu_items = [e for e in profile.get("education", []) if e != "Not detected"]
    exp_items = [e for e in profile.get("experience", []) if e != "Not detected"]
    has_name = profile.get("name", "Not detected") != "Not detected"
    has_email = profile.get("email", "Not detected") != "Not detected"
    has_phone = profile.get("phone", "Not detected") != "Not detected"
    text_length = len(resume_text.strip())

    target_role = match.get("target_role", "") if has_match else ""
    match_score = match.get("score", 0) if has_match else 0
    match_missing = match.get("missing", []) if has_match else []
    jd_score = jd_comparison.get("score", 0) if has_jd else 0
    jd_missing = jd_comparison.get("missing", []) if has_jd else []
    jd_matched = jd_comparison.get("matched", []) if has_jd else []

    summary_focus = _build_summary_focus(
        target_role, skills, match_score, jd_score, has_jd
    )
    keyword_additions = _build_keyword_additions(match_missing, jd_missing, skills)
    bullet_improvements = _build_bullet_improvements(
        exp_items, match_score, jd_score, target_role, has_jd
    )
    section_improvements = _build_section_improvements(
        has_name, has_email, has_phone, skills, edu_items, exp_items, text_length
    )
    ats_notes = _build_ats_notes(match_score, jd_score, has_match, has_jd, skills)

    return {
        "summary_focus": summary_focus,
        "keyword_additions": keyword_additions,
        "bullet_improvements": bullet_improvements,
        "section_improvements": section_improvements,
        "ats_notes": ats_notes,
    }


def _build_summary_focus(target_role, skills, match_score, jd_score, has_jd):
    """Build summary/objective focus suggestions."""
    items = []
    if target_role:
        items.append(
            f"Lead with a summary statement that positions you as a "
            f'strong candidate for "{target_role}".'
        )
    else:
        items.append(
            "Add a professional summary at the top of your resume "
            "that highlights your strongest qualifications."
        )

    if skills:
        top_skills = ", ".join(skills[:5])
        items.append(f"Emphasize your top skills early in the summary: {top_skills}.")

    if has_jd and jd_score < 40:
        items.append(
            "Your resume has low overlap with the job description. "
            "Rewrite the summary to mirror the language used in the listing."
        )
    elif has_jd and jd_score < 70:
        items.append(
            "Moderate JD overlap — tighten your summary to echo "
            "specific terms from the job description."
        )

    if match_score >= 70:
        items.append(
            "Your target-role alignment is strong. "
            "Keep the summary focused and concise."
        )

    if not items:
        items.append("Consider opening with a clear, targeted summary statement.")

    return items


def _build_keyword_additions(match_missing, jd_missing, current_skills):
    """Suggest keywords to add to the resume."""
    seen = {s.lower() for s in current_skills}
    additions = []

    # Combine missing from both match and JD, deduplicated
    all_missing = []
    for kw in match_missing:
        if kw.lower() not in seen:
            all_missing.append(kw)
            seen.add(kw.lower())
    for kw in jd_missing:
        if kw.lower() not in seen:
            all_missing.append(kw)
            seen.add(kw.lower())

    for kw in all_missing[:8]:
        additions.append(
            f'Add "{kw}" to your skills or experience sections '
            f"if you have relevant experience."
        )

    if not additions:
        additions.append(
            "No critical keyword gaps detected. "
            "Keep your skills section up to date with tools you actively use."
        )

    return additions


def _build_bullet_improvements(exp_items, match_score, jd_score, target_role, has_jd):
    """Suggest bullet-point improvements for experience section."""
    items = []

    if len(exp_items) == 0:
        items.append(
            "Add clear experience entries with bullet points. "
            "Use the format: Action verb + task + measurable result."
        )
        items.append(
            'Example: "Reduced API response time by 40% by implementing '
            'caching with Redis."'
        )
    elif len(exp_items) < 3:
        items.append(
            "Your experience section appears light. "
            "Expand each role with 3–5 outcome-focused bullet points."
        )
        items.append(
            "Start each bullet with a strong action verb: "
            "Led, Built, Designed, Implemented, Optimized, Delivered."
        )
    else:
        items.append(
            "Review each bullet point — ensure they start with action verbs "
            "and include specific outcomes or metrics where possible."
        )

    if has_jd and jd_score < 50:
        items.append(
            "Rewrite bullets to incorporate language from the job description "
            "where your experience genuinely applies."
        )

    if target_role and match_score < 40:
        items.append(
            f'Your match score for "{target_role}" is low. '
            f"Reframe existing accomplishments to highlight relevance "
            f"to this role."
        )

    items.append(
        "Quantify achievements where possible — "
        "use numbers, percentages, and timeframes."
    )

    return items


def _build_section_improvements(
    has_name, has_email, has_phone, skills, edu_items, exp_items, text_length
):
    """Suggest structural section improvements."""
    items = []

    if not has_name or not has_email or not has_phone:
        missing_contact = []
        if not has_name:
            missing_contact.append("full name")
        if not has_email:
            missing_contact.append("email")
        if not has_phone:
            missing_contact.append("phone number")
        items.append(
            f"Add missing contact details at the top: {', '.join(missing_contact)}."
        )

    if len(skills) < 3:
        items.append(
            "Create a dedicated Skills section listing 6–12 relevant tools, "
            "languages, and technologies. Use a simple comma-separated or "
            "column format for ATS readability."
        )
    elif len(skills) < 6:
        items.append(
            "Expand your Skills section — aim for 8–12 items covering "
            "technical tools, soft skills, and domain expertise."
        )

    if len(edu_items) == 0:
        items.append(
            "Add an Education section with your degree, institution, "
            "and graduation year."
        )

    if len(exp_items) == 0:
        items.append(
            "Add a Work Experience section with job titles, company names, "
            "dates, and bullet-pointed accomplishments."
        )

    if text_length < 300:
        items.append(
            "Your resume is very short. Most competitive resumes are "
            "at least one full page. Expand your content."
        )

    items.append(
        "Use consistent formatting: same font, clear section headings, "
        "and standard date formats (e.g., Jan 2022 – Present)."
    )

    items.append(
        "Avoid graphics, tables, and columns — "
        "many ATS systems cannot parse them correctly."
    )

    return items


def _build_ats_notes(match_score, jd_score, has_match, has_jd, skills):
    """Build ATS-specific notes and tips."""
    notes = []

    if has_jd and has_match:
        combined = (match_score + jd_score) / 2
        if combined >= 70:
            notes.append(
                "Your resume has strong overlap with both the target role "
                "and the job description. Focus on polish and formatting."
            )
        elif combined >= 40:
            notes.append(
                "Moderate ATS alignment. Fill keyword gaps and "
                "strengthen your bullet points to improve your score."
            )
        else:
            notes.append(
                "Low ATS alignment. Your resume likely lacks enough keyword "
                "overlap to pass automated screening. Significant tailoring "
                "is recommended."
            )
    elif has_jd:
        if jd_score >= 70:
            notes.append(
                "Strong overlap with the job description. "
                "Your resume should perform well in ATS screening."
            )
        elif jd_score >= 40:
            notes.append(
                "Moderate overlap with the job description. "
                "Address missing keywords to improve ATS pass-through."
            )
        else:
            notes.append(
                "Low overlap with the job description. "
                "Your resume may be filtered out by ATS systems. "
                "Consider a targeted rewrite."
            )
    elif has_match:
        if match_score >= 70:
            notes.append(
                "Strong target-role alignment. Ensure your formatting "
                "is ATS-friendly to maximize your chances."
            )
        elif match_score >= 40:
            notes.append(
                "Moderate target-role alignment. Add missing keywords "
                "and strengthen experience bullets."
            )
        else:
            notes.append(
                "Low target-role alignment. A significant rewrite "
                "may be needed to pass ATS screening for this role."
            )
    else:
        notes.append(
            "No target role or job description provided. "
            "For best ATS results, always tailor your resume to each application."
        )

    notes.append(
        "Use a clean, single-column layout with standard section headings "
        "(Summary, Experience, Skills, Education)."
    )

    notes.append(
        "Save your resume as a .pdf or .docx — these formats are "
        "most widely supported by ATS systems."
    )

    if len(skills) > 0:
        notes.append(
            "Place your Skills section near the top of your resume "
            "so ATS scanners find keywords early."
        )

    return notes
