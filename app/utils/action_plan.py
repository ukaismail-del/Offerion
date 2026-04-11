def generate_action_plan(
    scorecard=None, feedback=None, rewrite=None, tailored=None, jd_comparison=None
):
    """Generate a prioritized action plan based on analysis results.

    Returns a dict with top_priority, quick_wins, next_revision_steps,
    and final_checklist. Returns None if no useful input is available.
    """
    if not scorecard and not feedback:
        return None

    scores = scorecard.get("scores", {}) if scorecard else {}
    overall = scores.get("overall", 50)

    top_priority = _build_top_priority(scores, feedback, jd_comparison)
    quick_wins = _build_quick_wins(scores, feedback, jd_comparison, rewrite)
    next_revision_steps = _build_next_steps(scores, rewrite, tailored, jd_comparison)
    final_checklist = _build_checklist(scores, feedback, tailored, overall)

    return {
        "top_priority": top_priority,
        "quick_wins": quick_wins,
        "next_revision_steps": next_revision_steps,
        "final_checklist": final_checklist,
    }


def _build_top_priority(scores, feedback, jd_comparison):
    contact = scores.get("contact_info", 100)
    skills = scores.get("skills_coverage", 50)
    experience = scores.get("experience_strength", 50)
    ats = scores.get("ats_alignment", 50)

    if contact < 50:
        return "Fix your contact information first \u2014 missing name, email, or phone makes your resume unusable."
    if skills < 40:
        return "Expand your skills section urgently \u2014 ATS systems rely on keyword matches to surface your resume."
    if jd_comparison and jd_comparison.get("score", 100) < 30:
        return "Your resume has very low overlap with the job description \u2014 prioritize adding matching keywords."
    if ats < 40:
        return "Improve ATS alignment \u2014 your resume is not matching enough target keywords to pass automated screening."
    if experience < 40:
        return "Strengthen your experience section \u2014 add more detail, bullet points, and measurable outcomes."
    if skills < 60:
        return "Add more relevant skills to improve keyword coverage and ATS pass rate."
    if ats < 60:
        return (
            "Tighten keyword alignment with your target role to improve match scoring."
        )

    return "Your resume is in good shape \u2014 focus on polishing language and tailoring to each specific application."


def _build_quick_wins(scores, feedback, jd_comparison, rewrite):
    wins = []

    contact = scores.get("contact_info", 100)
    if contact < 80:
        wins.append(
            "Add any missing contact details (name, email, phone) at the top of your resume."
        )

    if feedback:
        gaps = feedback.get("gaps", [])
        if gaps:
            wins.append(gaps[0])

    if jd_comparison and jd_comparison.get("missing"):
        missing = jd_comparison["missing"][:3]
        kw_str = ", ".join(missing)
        wins.append(f"Add these JD keywords where truthfully applicable: {kw_str}.")

    skills = scores.get("skills_coverage", 50)
    if skills < 60:
        wins.append(
            "List at least 8\u201310 relevant skills in a dedicated Skills section."
        )

    if rewrite and rewrite.get("keyword_additions"):
        first_kw = rewrite["keyword_additions"][0]
        if len(wins) < 5:
            wins.append(f"Keyword to add: {first_kw}")

    if not wins:
        wins.append("Review your professional summary for clarity and role alignment.")
        wins.append("Ensure all bullet points start with strong action verbs.")
        wins.append("Double-check formatting consistency across all sections.")

    return wins[:5]


def _build_next_steps(scores, rewrite, tailored, jd_comparison):
    steps = []

    ats = scores.get("ats_alignment", 50)
    experience = scores.get("experience_strength", 50)

    if experience < 60:
        steps.append(
            "Rewrite experience bullets with measurable outcomes (numbers, percentages, timeframes)."
        )

    if ats < 60:
        steps.append(
            "Align your summary and bullet language with the target role terminology."
        )

    if rewrite and rewrite.get("bullet_improvements"):
        steps.append(rewrite["bullet_improvements"][0])

    if tailored and tailored.get("experience_focus_points"):
        focus = tailored["experience_focus_points"][0]
        if len(steps) < 5:
            steps.append(focus)

    if jd_comparison and jd_comparison.get("score", 100) < 60:
        steps.append(
            "Restructure your resume to mirror the job description's priority areas."
        )

    if rewrite and rewrite.get("section_improvements"):
        for item in rewrite["section_improvements"][:1]:
            if len(steps) < 5:
                steps.append(item)

    if not steps:
        steps.append("Fine-tune your professional summary to match each application.")
        steps.append("Reorder experience entries so the most relevant appears first.")
        steps.append("Proofread for consistency in tense, formatting, and punctuation.")

    return steps[:5]


def _build_checklist(scores, feedback, tailored, overall):
    checklist = []

    contact = scores.get("contact_info", 100)
    checklist.append(
        {
            "label": "Contact info complete (name, email, phone)",
            "done": contact >= 80,
        }
    )

    skills_score = scores.get("skills_coverage", 0)
    checklist.append(
        {
            "label": "Skills section has 8+ relevant keywords",
            "done": skills_score >= 60,
        }
    )

    exp_score = scores.get("experience_strength", 0)
    checklist.append(
        {
            "label": "Experience bullets include measurable outcomes",
            "done": exp_score >= 60,
        }
    )

    edu_score = scores.get("education_completeness", 0)
    checklist.append(
        {
            "label": "Education section is present and complete",
            "done": edu_score >= 60,
        }
    )

    ats_score = scores.get("ats_alignment", 0)
    checklist.append(
        {
            "label": "ATS keyword alignment is adequate",
            "done": ats_score >= 60,
        }
    )

    checklist.append(
        {
            "label": "Resume saved as a clean PDF before submitting",
            "done": False,
        }
    )

    return checklist[:6]
