from datetime import datetime


def build_tailored_brief(tailored):
    """Build a plain-text tailored resume brief from tailored analysis data.

    Returns a formatted string ready for download.
    """
    lines = []
    sep = "=" * 60
    sub = "-" * 40

    lines.append(sep)
    lines.append("OFFERION TAILORED RESUME BRIEF")
    lines.append(sep)
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # --- Target Title ---
    lines.append(sub)
    lines.append("TARGET TITLE")
    lines.append(sub)
    lines.append(tailored.get("target_title", "N/A"))
    lines.append("")

    # --- Professional Summary ---
    lines.append(sub)
    lines.append("PROFESSIONAL SUMMARY GUIDANCE")
    lines.append(sub)
    for item in tailored.get("professional_summary", []):
        lines.append(f"  > {item}")
    lines.append("")

    # --- Priority Keywords ---
    keywords = tailored.get("priority_keywords", [])
    if keywords:
        lines.append(sub)
        lines.append("PRIORITY KEYWORDS")
        lines.append(sub)
        for kw in keywords:
            lines.append(
                f"  [{kw['status'].upper()}] {kw['keyword']} "
                f"\u2014 {kw['action']}"
            )
        lines.append("")

    # --- Experience Focus Points ---
    lines.append(sub)
    lines.append("EXPERIENCE FOCUS POINTS")
    lines.append(sub)
    for item in tailored.get("experience_focus_points", []):
        lines.append(f"  * {item}")
    lines.append("")

    # --- Skills to Feature ---
    skills = tailored.get("skills_to_feature", [])
    if skills:
        lines.append(sub)
        lines.append("SKILLS TO FEATURE")
        lines.append(sub)
        for sf in skills:
            lines.append(
                f"  [{sf['priority'].upper()}] {sf['skill']} "
                f"\u2014 {sf['reason']}"
            )
        lines.append("")

    # --- Section Focus ---
    lines.append(sub)
    lines.append("SECTION FOCUS")
    lines.append(sub)
    for item in tailored.get("section_focus", []):
        lines.append(f"  # {item}")
    lines.append("")

    # --- Tailoring Notes ---
    lines.append(sub)
    lines.append("TAILORING NOTES")
    lines.append(sub)
    for item in tailored.get("tailoring_notes", []):
        lines.append(f"  i {item}")
    lines.append("")

    lines.append(sep)
    lines.append("END OF TAILORED BRIEF")
    lines.append(sep)

    return "\n".join(lines)
