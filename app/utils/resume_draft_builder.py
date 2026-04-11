from datetime import datetime


def build_resume_draft(
    profile=None,
    tailored=None,
    rewrite=None,
    action_plan=None,
    match=None,
    jd_comparison=None,
):
    """Build a plain-text structured resume draft.

    Uses analysis outputs to create a guided editing template.
    Returns None if insufficient data is available.
    """
    if not profile and not tailored:
        return None

    lines = []
    sep = "=" * 60
    sub = "-" * 40

    lines.append(sep)
    lines.append("OFFERION STRUCTURED RESUME DRAFT")
    lines.append(sep)
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(
        "This is a guided template — fill in real details from your experience."
    )
    lines.append("")

    # --- Name & Contact ---
    lines.append(sub)
    lines.append("NAME & CONTACT INFORMATION")
    lines.append(sub)
    if profile:
        name = profile.get("name", "Not detected")
        email = profile.get("email", "Not detected")
        phone = profile.get("phone", "Not detected")
        lines.append(name if name != "Not detected" else "[Your Full Name]")
        lines.append(email if email != "Not detected" else "[your.email@example.com]")
        lines.append(phone if phone != "Not detected" else "[+1-XXX-XXX-XXXX]")
    else:
        lines.append("[Your Full Name]")
        lines.append("[your.email@example.com]")
        lines.append("[+1-XXX-XXX-XXXX]")
    lines.append("[City, State] | [LinkedIn URL]")
    lines.append("")

    # --- Target Title ---
    target_title = None
    if tailored:
        target_title = tailored.get("target_title")
    if not target_title and match:
        target_title = match.get("target_role")
    lines.append(sub)
    lines.append("TARGET TITLE")
    lines.append(sub)
    lines.append(target_title if target_title else "[Target Job Title]")
    lines.append("")

    # --- Professional Summary ---
    lines.append(sub)
    lines.append("PROFESSIONAL SUMMARY")
    lines.append(sub)
    if tailored and tailored.get("professional_summary"):
        lines.append("Use these guidance points to write your summary:")
        for item in tailored["professional_summary"]:
            lines.append(f"  > {item}")
        lines.append("")
        lines.append("[Write 2-3 sentences here based on the guidance above.]")
    elif rewrite and rewrite.get("summary_focus"):
        lines.append("Focus areas for your summary:")
        for item in rewrite["summary_focus"]:
            lines.append(f"  > {item}")
        lines.append("")
        lines.append("[Write 2-3 sentences here based on the focus areas above.]")
    else:
        lines.append(
            "[Write a 2-3 sentence professional summary highlighting your "
            "key strengths and target role alignment.]"
        )
    lines.append("")

    # --- Core Skills ---
    lines.append(sub)
    lines.append("CORE SKILLS")
    lines.append(sub)
    if tailored and tailored.get("skills_to_feature"):
        for sf in tailored["skills_to_feature"]:
            priority = sf.get("priority", "medium").upper()
            lines.append(f"  [{priority}] {sf['skill']} — {sf.get('reason', '')}")
    elif profile and profile.get("skills"):
        for skill in profile["skills"]:
            lines.append(f"  • {skill}")
    else:
        lines.append("[List 8-10 relevant skills, separated by commas or bullets]")

    if tailored and tailored.get("priority_keywords"):
        missing_kw = [
            kw["keyword"]
            for kw in tailored["priority_keywords"]
            if kw.get("status") == "missing"
        ]
        if missing_kw:
            lines.append("")
            lines.append("Keywords to add (currently missing from resume):")
            for kw in missing_kw:
                lines.append(f"  + {kw}")
    elif jd_comparison and jd_comparison.get("missing"):
        lines.append("")
        lines.append("Keywords from job description to consider adding:")
        for kw in jd_comparison["missing"][:8]:
            lines.append(f"  + {kw}")
    lines.append("")

    # --- Experience ---
    lines.append(sub)
    lines.append("EXPERIENCE")
    lines.append(sub)
    if tailored and tailored.get("experience_focus_points"):
        lines.append("Focus points for your experience section:")
        for item in tailored["experience_focus_points"]:
            lines.append(f"  * {item}")
        lines.append("")

    lines.append("[Job Title] — [Company Name]")
    lines.append("[Start Date] – [End Date]")
    lines.append("  • [Add 2-3 quantified bullet points here]")
    lines.append("  • [Use action verbs: Led, Built, Improved, Delivered...]")
    lines.append("  • [Insert relevant project outcome with numbers here]")
    lines.append("")
    lines.append("[Job Title] — [Company Name]")
    lines.append("[Start Date] – [End Date]")
    lines.append("  • [Add 2-3 quantified bullet points here]")
    lines.append("  • [Insert relevant achievement or result here]")
    lines.append("")

    if rewrite and rewrite.get("bullet_improvements"):
        lines.append("Bullet improvement suggestions:")
        for item in rewrite["bullet_improvements"]:
            lines.append(f"  ~ {item}")
        lines.append("")

    # --- Education ---
    lines.append(sub)
    lines.append("EDUCATION")
    lines.append(sub)
    if profile and profile.get("education"):
        for edu in profile["education"]:
            lines.append(f"  {edu}")
    else:
        lines.append("[Degree] — [Institution]")
        lines.append("[Graduation Year]")
    lines.append("")

    # --- ATS Alignment Notes ---
    if rewrite:
        lines.append(sub)
        lines.append("ATS ALIGNMENT NOTES")
        lines.append(sub)
        if rewrite.get("keyword_additions"):
            lines.append("Keywords to weave in:")
            for item in rewrite["keyword_additions"]:
                lines.append(f"  + {item}")
            lines.append("")
        if rewrite.get("ats_notes"):
            lines.append("ATS tips:")
            for item in rewrite["ats_notes"]:
                lines.append(f"  i {item}")
            lines.append("")

    # --- Revision Checklist ---
    if action_plan and action_plan.get("final_checklist"):
        lines.append(sub)
        lines.append("REVISION CHECKLIST")
        lines.append(sub)
        for check in action_plan["final_checklist"]:
            status = "DONE" if check.get("done") else "TODO"
            lines.append(f"  [{status}] {check.get('label', '')}")
        lines.append("")

    # --- Closing ---
    lines.append(sep)
    lines.append("END OF DRAFT")
    lines.append(sep)
    lines.append("")
    lines.append("Fill in all bracketed placeholders with your real information.")
    lines.append("Do not submit this template as-is.")
    lines.append("Generated by Offerion — offerion.onrender.com")

    return "\n".join(lines)
