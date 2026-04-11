"""M30 — Match Score Explanation.

Explains the match score in plain English: strengths, gaps, summary.
Deterministic — no AI APIs.
"""


def explain_match(match=None, profile=None, tailored=None, rewrite=None):
    """Generate a plain-English explanation of the match score.

    Returns a dict with score, strengths, gaps, summary, confidence_note.
    Returns None if no match data exists.
    """
    if not match:
        return None

    score = match.get("score", 0)
    strengths = _identify_strengths(match, profile, tailored)
    gaps = _identify_gaps(match, profile, tailored, rewrite)
    summary = _build_summary(score, strengths, gaps, match)
    confidence_note = (
        "This estimate is based on keyword alignment and structured "
        "resume signals. It does not reflect recruiter or hiring decisions."
    )

    return {
        "score": score,
        "strengths": strengths,
        "gaps": gaps,
        "summary": summary,
        "confidence_note": confidence_note,
    }


def _identify_strengths(match, profile, tailored):
    strengths = []

    matched = match.get("matched_keywords", [])
    if matched:
        top = matched[:5]
        strengths.append(
            f"Strong keyword alignment: {', '.join(top)}"
        )

    if profile and profile.get("skills"):
        count = len(profile["skills"])
        if count >= 5:
            strengths.append(
                f"Solid skills inventory ({count} skills detected)"
            )

    if tailored and tailored.get("skills_to_feature"):
        high_pri = [s["skill"] for s in tailored["skills_to_feature"]
                    if s.get("priority") == "high"]
        if high_pri:
            strengths.append(
                f"High-priority skills present: {', '.join(high_pri[:4])}"
            )

    target = match.get("target_role", "")
    if profile and profile.get("name") and profile["name"] != "Not detected":
        strengths.append("Contact information detected in resume")

    if tailored and tailored.get("professional_summary"):
        strengths.append("Professional summary content available for targeting")

    if not strengths:
        strengths.append("Resume parsed successfully with extractable content")

    return strengths


def _identify_gaps(match, profile, tailored, rewrite):
    gaps = []

    missing = match.get("missing_keywords", [])
    if missing:
        top_missing = missing[:5]
        gaps.append(
            f"Missing keywords: {', '.join(top_missing)}"
        )

    if rewrite and rewrite.get("keyword_additions"):
        adds = rewrite["keyword_additions"][:4]
        gaps.append(
            f"Keywords recommended for addition: {', '.join(adds)}"
        )

    if rewrite and rewrite.get("bullet_improvements"):
        gaps.append("Experience bullets need strengthening")

    score = match.get("score", 0)
    if score < 50:
        gaps.append("Overall keyword alignment is below average")
    elif score < 70:
        gaps.append("Keyword alignment is moderate — targeted improvements can help")

    if profile and profile.get("education"):
        if len(profile["education"]) == 0:
            gaps.append("No education entries detected")

    if not gaps:
        gaps.append("No major gaps identified at this stage")

    return gaps


def _build_summary(score, strengths, gaps, match):
    target = match.get("target_role", "the target role")
    level = match.get("level", "")

    if score >= 75:
        tone = "strong"
        outlook = "well-positioned"
    elif score >= 50:
        tone = "moderate"
        outlook = "partially aligned"
    else:
        tone = "developing"
        outlook = "in early alignment"

    return (
        f"Your resume shows {tone} alignment with the {target} role "
        f"(score: {score}/100). You are {outlook} for this position. "
        f"There are {len(strengths)} identified strengths and "
        f"{len(gaps)} areas for improvement."
    )
