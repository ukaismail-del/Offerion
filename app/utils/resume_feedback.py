def generate_feedback(resume_text, profile, match=None):
    """Generate resume improvement feedback based on profile and optional match data.

    Returns a dict with strengths, gaps, recommendations, and completeness.
    """
    strengths = []
    gaps = []
    recommendations = []
    completeness = []

    text_length = len(resume_text.strip())
    has_name = profile.get("name", "Not detected") != "Not detected"
    has_email = profile.get("email", "Not detected") != "Not detected"
    has_phone = profile.get("phone", "Not detected") != "Not detected"
    skills = [s for s in profile.get("skills", []) if s != "Not detected"]
    edu_items = [e for e in profile.get("education", []) if e != "Not detected"]
    exp_items = [e for e in profile.get("experience", []) if e != "Not detected"]

    # --- Completeness checks ---
    completeness.append(_check("Name detected", has_name))
    completeness.append(_check("Email detected", has_email))
    completeness.append(_check("Phone detected", has_phone))
    completeness.append(_check("Skills detected", len(skills) > 0))
    completeness.append(_check("Education indicators found", len(edu_items) > 0))
    completeness.append(_check("Experience indicators found", len(exp_items) > 0))
    completeness.append(_check("Resume text length adequate", text_length >= 200))

    # --- Strengths ---
    if has_email and has_phone:
        strengths.append("Contact information is present (email and phone).")
    elif has_email:
        strengths.append("Email address is present.")
    elif has_phone:
        strengths.append("Phone number is present.")

    if len(skills) >= 5:
        strengths.append(f"Strong skills section with {len(skills)} skills detected.")
    elif len(skills) >= 2:
        strengths.append(f"Skills section present with {len(skills)} skills detected.")

    if len(edu_items) >= 1:
        strengths.append("Education background is included.")

    if len(exp_items) >= 2:
        strengths.append(f"Multiple experience indicators found ({len(exp_items)}).")
    elif len(exp_items) == 1:
        strengths.append("At least one experience indicator detected.")

    if text_length >= 500:
        strengths.append("Resume has substantial content to work with.")

    if match and match.get("score", 0) >= 70:
        strengths.append(
            f"Strong alignment with target role \"{match['target_role']}\" "
            f"(score: {match['score']})."
        )
    elif match and match.get("score", 0) >= 40:
        strengths.append(
            f"Moderate alignment with target role \"{match['target_role']}\" "
            f"(score: {match['score']})."
        )

    # --- Gaps ---
    if not has_name:
        gaps.append("Name could not be detected from the resume.")
    if not has_email:
        gaps.append("No email address found.")
    if not has_phone:
        gaps.append("No phone number found.")
    if len(skills) == 0:
        gaps.append("No recognizable skills were detected.")
    elif len(skills) < 3:
        gaps.append(f"Only {len(skills)} skill(s) detected — consider listing more.")
    if len(edu_items) == 0:
        gaps.append("No education indicators found.")
    if len(exp_items) == 0:
        gaps.append("No experience indicators found.")
    if text_length < 200:
        gaps.append("Resume text is very short — it may be incomplete or poorly formatted.")

    if match:
        missing = match.get("missing", [])
        if missing:
            top_missing = ", ".join(missing[:5])
            gaps.append(f"Missing target keywords: {top_missing}.")

    # --- Recommendations ---
    if not has_email or not has_phone:
        recommendations.append(
            "Add complete contact information (email and phone) at the top of your resume."
        )

    if len(skills) < 5:
        recommendations.append(
            "Strengthen your skills section by listing specific tools, "
            "languages, and technologies you have used."
        )

    if len(exp_items) == 0:
        recommendations.append(
            "Add clear work experience entries with job titles, companies, "
            "dates, and outcome-focused bullet points."
        )
    elif len(exp_items) < 3:
        recommendations.append(
            "Expand your experience section with more detail — include measurable "
            "outcomes and specific responsibilities."
        )

    if len(edu_items) == 0:
        recommendations.append(
            "Include education details if applicable — degree, institution, "
            "and graduation year."
        )

    if match:
        missing = match.get("missing", [])
        if missing:
            top_missing = ", ".join(missing[:4])
            recommendations.append(
                f"Consider adding relevant experience or skills for: {top_missing} "
                f"(only where truthful and applicable)."
            )
        if match.get("score", 0) < 40:
            recommendations.append(
                f"Your match score for \"{match['target_role']}\" is low. "
                f"Review the job requirements and tailor your resume to highlight "
                f"relevant experience."
            )

    if text_length < 300:
        recommendations.append(
            "Your resume appears short. Add more detail to your experience "
            "and skills sections."
        )

    if not strengths:
        strengths.append("Resume uploaded and text extracted successfully.")
    if not gaps:
        gaps.append("No major gaps detected — your resume covers the basics well.")
    if not recommendations:
        recommendations.append(
            "Your resume looks solid. Keep it updated and tailored to each role."
        )

    return {
        "strengths": strengths,
        "gaps": gaps,
        "recommendations": recommendations,
        "completeness": completeness,
    }


def _check(label, passed):
    return {"label": label, "passed": passed}
