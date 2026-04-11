def generate_tailored_resume(
    resume_text, profile, match=None, jd_comparison=None, rewrite=None, scorecard=None
):
    """Generate a tailored resume draft outline based on analysis data.

    Returns a dict with target_title, professional_summary, priority_keywords,
    experience_focus_points, skills_to_feature, section_focus, and tailoring_notes.
    Returns None if there is not enough context (no profile or no target role/JD).
    """
    if not profile:
        return None

    has_match = match is not None
    has_jd = jd_comparison is not None

    # Need at least a target role or JD to produce a tailored version
    if not has_match and not has_jd:
        return None

    target_role = match.get("target_role", "") if has_match else ""
    skills = [s for s in profile.get("skills", []) if s != "Not detected"]
    exp_items = [e for e in profile.get("experience", []) if e != "Not detected"]
    edu_items = [e for e in profile.get("education", []) if e != "Not detected"]

    target_title = _build_target_title(target_role, jd_comparison)
    professional_summary = _build_summary(
        target_role, skills, exp_items, match, jd_comparison
    )
    priority_keywords = _build_priority_keywords(match, jd_comparison, skills)
    experience_focus_points = _build_experience_focus(
        exp_items, match, jd_comparison, target_role
    )
    skills_to_feature = _build_skills_to_feature(skills, match, jd_comparison)
    section_focus = _build_section_focus(
        profile, skills, exp_items, edu_items, scorecard
    )
    tailoring_notes = _build_tailoring_notes(match, jd_comparison, scorecard, rewrite)

    return {
        "target_title": target_title,
        "professional_summary": professional_summary,
        "priority_keywords": priority_keywords,
        "experience_focus_points": experience_focus_points,
        "skills_to_feature": skills_to_feature,
        "section_focus": section_focus,
        "tailoring_notes": tailoring_notes,
    }


def _build_target_title(target_role, jd_comparison):
    if target_role:
        return target_role
    return "Role from Job Description"


def _build_summary(target_role, skills, exp_items, match, jd_comparison):
    lines = []

    role_label = target_role if target_role else "the target role"

    if len(exp_items) >= 3:
        lines.append(
            f"Open with: Experienced professional with a track record in "
            f"areas relevant to {role_label}."
        )
    elif len(exp_items) >= 1:
        lines.append(
            f"Open with: Motivated professional seeking to contribute to "
            f"{role_label}."
        )
    else:
        lines.append(
            f"Open with: Detail-oriented candidate eager to apply skills "
            f"toward {role_label}."
        )

    if skills:
        top = ", ".join(skills[:5])
        lines.append(f"Highlight core competencies: {top}.")

    if match and match.get("matched"):
        matched_str = ", ".join(match["matched"][:4])
        lines.append(f"Emphasize demonstrated alignment: {matched_str}.")

    if jd_comparison and jd_comparison.get("matched"):
        jd_matched = ", ".join(jd_comparison["matched"][:4])
        lines.append(f"Mirror JD language by referencing: {jd_matched}.")

    lines.append("Close with a clear value statement about what you bring to the team.")

    return lines


def _build_priority_keywords(match, jd_comparison, current_skills):
    keywords = []
    seen = {s.lower() for s in current_skills}

    # Matched keywords should be featured prominently
    if match and match.get("matched"):
        for kw in match["matched"]:
            if kw.lower() not in seen:
                keywords.append(
                    {
                        "keyword": kw,
                        "status": "matched",
                        "action": "feature prominently",
                    }
                )
                seen.add(kw.lower())

    if jd_comparison and jd_comparison.get("matched"):
        for kw in jd_comparison["matched"]:
            if kw.lower() not in seen:
                keywords.append(
                    {
                        "keyword": kw,
                        "status": "matched",
                        "action": "feature prominently",
                    }
                )
                seen.add(kw.lower())

    # Missing keywords should be added if truthful
    if match and match.get("missing"):
        for kw in match["missing"][:5]:
            if kw.lower() not in seen:
                keywords.append(
                    {
                        "keyword": kw,
                        "status": "missing",
                        "action": "add if you have experience",
                    }
                )
                seen.add(kw.lower())

    if jd_comparison and jd_comparison.get("missing"):
        for kw in jd_comparison["missing"][:5]:
            if kw.lower() not in seen:
                keywords.append(
                    {
                        "keyword": kw,
                        "status": "missing",
                        "action": "add if you have experience",
                    }
                )
                seen.add(kw.lower())

    # Include current skills as "keep"
    for s in current_skills[:5]:
        if s.lower() not in seen:
            keywords.append(
                {"keyword": s, "status": "present", "action": "keep in skills section"}
            )
            seen.add(s.lower())

    return keywords[:12]


def _build_experience_focus(exp_items, match, jd_comparison, target_role):
    points = []

    role_label = target_role if target_role else "the target role"

    if exp_items:
        points.append(
            f"Lead with your most relevant experience for {role_label}. "
            f"Reorder entries so the strongest match appears first."
        )
        points.append(
            "For each role, write 3\u20135 bullet points starting with strong "
            "action verbs (Led, Built, Designed, Optimized, Delivered)."
        )
    else:
        points.append(
            "Add a Work Experience section. Even internships, projects, or "
            "volunteer work can demonstrate relevant skills."
        )

    if match and match.get("missing"):
        missing_str = ", ".join(match["missing"][:3])
        points.append(
            f"Look for ways to demonstrate experience with: {missing_str}. "
            f"Reframe existing accomplishments where truthfully applicable."
        )

    if jd_comparison and jd_comparison.get("missing"):
        jd_missing = [
            k
            for k in jd_comparison["missing"][:3]
            if not match or k not in match.get("missing", [])
        ]
        if jd_missing:
            jd_str = ", ".join(jd_missing)
            points.append(
                f"The job description also mentions: {jd_str}. "
                f"Incorporate these into bullet points where applicable."
            )

    points.append(
        "Quantify outcomes wherever possible \u2014 use numbers, percentages, "
        "dollar amounts, or timeframes."
    )

    return points


def _build_skills_to_feature(skills, match, jd_comparison):
    featured = []
    seen = set()

    # First: skills that are both in resume and matched
    matched_set = set()
    if match and match.get("matched"):
        matched_set.update(m.lower() for m in match["matched"])
    if jd_comparison and jd_comparison.get("matched"):
        matched_set.update(m.lower() for m in jd_comparison["matched"])

    for s in skills:
        if s.lower() in matched_set and s.lower() not in seen:
            featured.append(
                {
                    "skill": s,
                    "priority": "high",
                    "reason": "matches target requirements",
                }
            )
            seen.add(s.lower())

    # Then: remaining detected skills
    for s in skills:
        if s.lower() not in seen:
            featured.append(
                {"skill": s, "priority": "medium", "reason": "detected in resume"}
            )
            seen.add(s.lower())

    # Then: missing but important keywords to consider adding
    if match and match.get("missing"):
        for kw in match["missing"][:3]:
            if kw.lower() not in seen:
                featured.append(
                    {
                        "skill": kw,
                        "priority": "add",
                        "reason": "missing from resume \u2014 add if truthful",
                    }
                )
                seen.add(kw.lower())

    return featured[:10]


def _build_section_focus(profile, skills, exp_items, edu_items, scorecard):
    sections = []

    # Use scorecard to determine emphasis order
    if scorecard:
        scores = scorecard.get("scores", {})
        weak_areas = [(k, v) for k, v in scores.items() if k != "overall" and v < 60]
        weak_areas.sort(key=lambda x: x[1])

        area_map = {
            "contact_info": "Contact Information \u2014 ensure name, email, and phone are clearly visible at the top",
            "skills_coverage": "Skills Section \u2014 expand to 8\u201312 relevant items, group by category if needed",
            "experience_strength": "Work Experience \u2014 add more detail, bullet points, and measurable outcomes",
            "education_completeness": "Education \u2014 include degree, institution, and graduation year",
            "ats_alignment": "Keyword Optimization \u2014 align terminology with the job description",
        }

        if weak_areas:
            sections.append("Priority sections to strengthen (based on scorecard):")
            for area, score in weak_areas:
                if area in area_map:
                    sections.append(f"  \u2022 {area_map[area]} (score: {score}/100)")
        else:
            sections.append(
                "All sections score well. Focus on polish and tailoring language."
            )
    else:
        if len(skills) < 5:
            sections.append(
                "Skills Section \u2014 needs expansion with more relevant terms."
            )
        if len(exp_items) < 2:
            sections.append("Work Experience \u2014 needs more entries or detail.")
        if len(edu_items) == 0:
            sections.append("Education \u2014 add education background.")

    sections.append(
        "Professional Summary \u2014 place at the top, tailored to the target role."
    )
    sections.append("Skills \u2014 list directly below summary for quick ATS scanning.")

    return sections


def _build_tailoring_notes(match, jd_comparison, scorecard, rewrite):
    notes = []

    has_match = match is not None
    has_jd = jd_comparison is not None
    match_score = match.get("score", 0) if has_match else 0
    jd_score = jd_comparison.get("score", 0) if has_jd else 0

    if has_match and has_jd:
        avg = (match_score + jd_score) / 2
        if avg >= 70:
            notes.append(
                "Your resume already has strong alignment. "
                "Focus on fine-tuning language to mirror the exact terms "
                "used in the job description."
            )
        elif avg >= 40:
            notes.append(
                "Moderate alignment detected. Close the gap by incorporating "
                "missing keywords and strengthening your experience bullets."
            )
        else:
            notes.append(
                "Significant tailoring is needed. Consider restructuring "
                "your resume around the requirements in the job description."
            )
    elif has_match:
        if match_score >= 70:
            notes.append("Strong target-role fit. Minor tailoring should suffice.")
        elif match_score >= 40:
            notes.append(
                "Moderate fit \u2014 address the missing keywords and "
                "reframe experience toward the target role."
            )
        else:
            notes.append(
                "Low target-role fit. A significant rewrite focused on "
                "relevant experience is recommended."
            )
    elif has_jd:
        if jd_score >= 70:
            notes.append("Strong JD overlap. Polish formatting and keyword placement.")
        else:
            notes.append(
                "Tailor your resume to better reflect the language and "
                "requirements in the job description."
            )

    notes.append(
        "Always keep content truthful \u2014 reframe real experience, "
        "never fabricate roles or achievements."
    )

    if scorecard:
        overall = scorecard.get("scores", {}).get("overall", 0)
        if overall < 50:
            notes.append(
                "Your overall resume strength is below average. "
                "Prioritize adding content to weak sections before tailoring."
            )

    notes.append(
        "Save as a new file (e.g., resume_[company].pdf) so you keep "
        "your master resume intact."
    )

    return notes
