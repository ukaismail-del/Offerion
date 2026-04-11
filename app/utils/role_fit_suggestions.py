"""M33 — Role-Fit Improvement Suggestions.

Gives strategic suggestions for improving fit for the target role.
Deterministic — no AI APIs.
"""


def suggest_role_fit(match=None, profile=None, tailored=None,
                     rewrite=None, enhanced_resume=None):
    """Generate role-fit improvement suggestions.

    Returns a dict with target_title, fit_level, improvement_suggestions,
    positioning_advice, next_step.  Returns None if no match data.
    """
    if not match:
        return None

    score = match.get("score", 0)
    target_title = _resolve_title(match, tailored, enhanced_resume)
    fit_level = _classify_fit(score)
    suggestions = _build_suggestions(match, profile, tailored, rewrite)
    advice = _build_positioning(match, profile, tailored, rewrite)
    next_step = _build_next_step(fit_level, target_title)

    return {
        "target_title": target_title,
        "fit_level": fit_level,
        "improvement_suggestions": suggestions,
        "positioning_advice": advice,
        "next_step": next_step,
    }


def _resolve_title(match, tailored, enhanced_resume):
    if enhanced_resume and enhanced_resume.get("target_title"):
        return enhanced_resume["target_title"]
    if tailored and tailored.get("target_title"):
        return tailored["target_title"]
    return match.get("target_role", "Target Role")


def _classify_fit(score):
    if score >= 75:
        return "Strong"
    elif score >= 50:
        return "Moderate"
    else:
        return "Developing"


def _build_suggestions(match, profile, tailored, rewrite):
    suggestions = []

    # Domain tools
    if tailored and tailored.get("skills_to_feature"):
        high = [s["skill"] for s in tailored["skills_to_feature"]
                if s.get("priority") == "high"]
        if high:
            suggestions.append(
                f"Emphasize domain-relevant tools: {', '.join(high[:4])}"
            )

    # Transferable experience
    if match.get("missing_keywords"):
        suggestions.append(
            "Reframe transferable experience to bridge keyword gaps"
        )

    # Action verbs
    if rewrite and rewrite.get("bullet_improvements"):
        suggestions.append(
            "Improve action verbs to show ownership and impact"
        )

    # Scale / collaboration
    if tailored and tailored.get("experience_focus_points"):
        suggestions.append(
            "Show scale, ownership, or collaboration where your experience supports it"
        )

    # Summary alignment
    if rewrite and rewrite.get("summary_focus"):
        suggestions.append(
            "Align your summary more tightly with the target role language"
        )

    if not suggestions:
        suggestions.append(
            "Continue refining your resume around the target role requirements"
        )

    return suggestions[:5]


def _build_positioning(match, profile, tailored, rewrite):
    advice = []
    target = match.get("target_role", "the role")
    score = match.get("score", 0)

    if score >= 75:
        advice.append(
            f"Your profile already shows strong alignment with {target}. "
            f"Focus on polishing details rather than major changes."
        )
    elif score >= 50:
        advice.append(
            f"You have a solid foundation for {target}. Targeted adjustments "
            f"to keywords and experience framing can meaningfully improve fit."
        )
    else:
        advice.append(
            f"Building toward {target} will require highlighting transferable "
            f"skills and strengthening role-specific language throughout."
        )

    # Keyword positioning
    matched = match.get("matched_keywords", [])
    if matched:
        advice.append(
            f"Leverage your strongest alignments ({', '.join(matched[:3])}) "
            f"prominently in your summary and skills sections."
        )

    # Education positioning
    if profile and profile.get("education"):
        if profile["education"]:
            advice.append(
                "Position your education to support role credibility where relevant"
            )

    return advice[:4]


def _build_next_step(fit_level, target_title):
    if fit_level == "Strong":
        return (
            f"Your resume is well-aligned for {target_title}. Consider "
            f"enhancing your cover letter and saving an application package."
        )
    elif fit_level == "Moderate":
        return (
            f"Address the priority fixes and missing keywords identified "
            f"above, then re-enhance your resume for {target_title}."
        )
    else:
        return (
            f"Focus on building keyword alignment and reframing experience "
            f"for {target_title}. Use the rewrite guidance and priority "
            f"fixes as your roadmap."
        )
