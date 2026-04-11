"""M32 — Priority Fixes / Quick Wins.

Identifies the fastest actions most likely to improve resume-job fit.
Deterministic — no AI APIs.
"""


def generate_priority_fixes(match=None, profile=None, tailored=None,
                            rewrite=None, scorecard=None):
    """Generate prioritised fix recommendations.

    Returns a dict with top_priority, quick_wins, section_targets.
    Returns None if insufficient data.
    """
    if not match and not rewrite:
        return None

    top_priority = _build_top_priority(match, tailored, rewrite)
    quick_wins = _build_quick_wins(match, profile, rewrite, scorecard)
    section_targets = _build_section_targets(match, tailored, rewrite)

    return {
        "top_priority": top_priority,
        "quick_wins": quick_wins,
        "section_targets": section_targets,
    }


def _build_top_priority(match, tailored, rewrite):
    items = []

    # Missing high-value keywords
    if match and match.get("missing_keywords"):
        top_kw = match["missing_keywords"][:3]
        items.append(
            f"Add missing keywords to your resume: {', '.join(top_kw)}"
        )

    # Summary alignment
    if rewrite and rewrite.get("summary_focus"):
        items.append(
            "Rewrite your professional summary to align with the target role"
        )

    # Target title in summary
    target = None
    if match:
        target = match.get("target_role")
    if tailored:
        target = tailored.get("target_title") or target
    if target:
        items.append(
            f"Include \"{target}\" in your summary or headline"
        )

    if not items:
        items.append("Continue refining your resume for stronger alignment")

    return items[:4]


def _build_quick_wins(match, profile, rewrite, scorecard):
    wins = []

    # ATS formatting
    if rewrite and rewrite.get("ats_notes"):
        for note in rewrite["ats_notes"][:2]:
            wins.append(note)

    # Bullet improvements
    if rewrite and rewrite.get("bullet_improvements"):
        wins.append("Strengthen experience bullets with action verbs and metrics")

    # Skills count
    if profile and profile.get("skills"):
        if len(profile["skills"]) < 5:
            wins.append("Expand your skills section — aim for 8-12 relevant skills")

    # Scorecard-based
    if scorecard and scorecard.get("section_scores"):
        for sec, data in scorecard["section_scores"].items():
            sc = data.get("score", 100) if isinstance(data, dict) else data
            if isinstance(sc, (int, float)) and sc < 50:
                wins.append(f"Improve your {sec} section (currently weak)")

    if not wins:
        wins.append("Your resume is in good shape — focus on targeted keyword additions")

    return wins[:5]


def _build_section_targets(match, tailored, rewrite):
    targets = []

    if rewrite and rewrite.get("summary_focus"):
        targets.append({
            "section": "Summary",
            "action": "Align language with target role requirements",
        })

    if match and match.get("missing_keywords"):
        targets.append({
            "section": "Skills",
            "action": "Add missing high-value keywords from job requirements",
        })

    if rewrite and rewrite.get("bullet_improvements"):
        targets.append({
            "section": "Experience",
            "action": "Use stronger action verbs and quantify achievements",
        })

    if tailored and tailored.get("experience_focus_points"):
        targets.append({
            "section": "Experience",
            "action": "Focus bullets on: " + "; ".join(
                tailored["experience_focus_points"][:2]
            ),
        })

    if not targets:
        targets.append({
            "section": "General",
            "action": "Review all sections for keyword and tone alignment",
        })

    # Deduplicate by section
    seen = set()
    unique = []
    for t in targets:
        if t["section"] not in seen:
            seen.add(t["section"])
            unique.append(t)

    return unique[:5]
