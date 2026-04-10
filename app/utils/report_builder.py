from datetime import datetime


def build_report(result, profile, match, suggestions, feedback):
    """Build a plain-text analysis report from Offerion results.

    Returns a formatted string ready for download.
    """
    lines = []
    sep = "=" * 60
    sub = "-" * 40

    lines.append(sep)
    lines.append("OFFERION ANALYSIS REPORT")
    lines.append(sep)
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # --- File Information ---
    lines.append(sub)
    lines.append("FILE INFORMATION")
    lines.append(sub)
    if result:
        lines.append(f"Filename : {result.get('filename', 'N/A')}")
        lines.append(f"File Type: {result.get('filetype', 'N/A')}")
        lines.append(f"Status   : {result.get('status', 'N/A')}")
    else:
        lines.append("No file information available.")
    lines.append("")

    # --- Resume Profile Summary ---
    lines.append(sub)
    lines.append("RESUME PROFILE SUMMARY")
    lines.append(sub)
    if profile:
        lines.append(f"Name : {profile.get('name', 'Not detected')}")
        lines.append(f"Email: {profile.get('email', 'Not detected')}")
        lines.append(f"Phone: {profile.get('phone', 'Not detected')}")
        lines.append("")

        skills = profile.get("skills", [])
        if skills and skills != ["Not detected"]:
            lines.append("Skills:")
            for skill in skills:
                lines.append(f"  - {skill}")
        else:
            lines.append("Skills: Not detected")
        lines.append("")

        education = profile.get("education", [])
        if education and education != ["Not detected"]:
            lines.append("Education Indicators:")
            for item in education:
                lines.append(f"  - {item}")
        else:
            lines.append("Education Indicators: Not detected")
        lines.append("")

        experience = profile.get("experience", [])
        if experience and experience != ["Not detected"]:
            lines.append("Experience Indicators:")
            for item in experience:
                lines.append(f"  - {item}")
        else:
            lines.append("Experience Indicators: Not detected")
    else:
        lines.append("No profile data available.")
    lines.append("")

    # --- Match Analysis ---
    lines.append(sub)
    lines.append("MATCH ANALYSIS")
    lines.append(sub)
    if match:
        lines.append(f"Target Role     : {match.get('target_role', 'N/A')}")
        lines.append(f"Keywords Entered: {match.get('keywords_entered', 'N/A')}")
        lines.append(f"Match Score     : {match.get('score', 0)} / 100")
        lines.append(f"Match Level     : {match.get('level', 'N/A')}")
        lines.append("")

        matched = match.get("matched", [])
        if matched:
            lines.append("Matched Keywords:")
            for item in matched:
                lines.append(f"  + {item}")
        else:
            lines.append("Matched Keywords: None")

        missing = match.get("missing", [])
        if missing:
            lines.append("Missing Keywords:")
            for item in missing:
                lines.append(f"  - {item}")
        else:
            lines.append("Missing Keywords: None")

        lines.append("")
        lines.append(f"Explanation: {match.get('explanation', '')}")
    else:
        lines.append("No target role was entered. Match analysis was skipped.")
    lines.append("")

    # --- Suggested Roles ---
    lines.append(sub)
    lines.append("SUGGESTED ROLES")
    lines.append(sub)
    if suggestions:
        for i, s in enumerate(suggestions, 1):
            lines.append(f"{i}. {s.get('role', 'N/A')}")
            lines.append(f"   Score : {s.get('score', 0)} / 100 — {s.get('level', 'N/A')}")
            matched_items = s.get("matched", [])
            if matched_items:
                lines.append(f"   Matched: {', '.join(matched_items)}")
            lines.append(f"   Reason : {s.get('reason', '')}")
            lines.append("")
    else:
        lines.append("No role suggestions available.")
    lines.append("")

    # --- Resume Improvement Guidance ---
    lines.append(sub)
    lines.append("RESUME IMPROVEMENT GUIDANCE")
    lines.append(sub)
    if feedback:
        lines.append("")
        lines.append("Strengths:")
        for item in feedback.get("strengths", []):
            lines.append(f"  [+] {item}")
        lines.append("")

        lines.append("Gaps:")
        for item in feedback.get("gaps", []):
            lines.append(f"  [!] {item}")
        lines.append("")

        lines.append("Recommendations:")
        for item in feedback.get("recommendations", []):
            lines.append(f"  [>] {item}")
        lines.append("")

        lines.append("Completeness:")
        for check in feedback.get("completeness", []):
            status = "PASS" if check.get("passed") else "FAIL"
            lines.append(f"  [{status}] {check.get('label', '')}")
    else:
        lines.append("No feedback data available.")
    lines.append("")

    lines.append(sep)
    lines.append("END OF REPORT")
    lines.append(sep)

    return "\n".join(lines)
