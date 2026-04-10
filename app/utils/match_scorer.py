import re


def score_match(resume_text, profile, target_role, target_keywords_raw=""):
    """Score how well a resume matches a target role and keywords.

    Returns a dict with score, level, matched, missing, explanation.
    """
    resume_lower = resume_text.lower()

    # Build the combined target keyword set
    target_keywords = _parse_keywords(target_keywords_raw)
    role_words = _parse_role_words(target_role)
    all_targets = list(
        dict.fromkeys(role_words + target_keywords)
    )  # dedupe, keep order

    # Get resume skills (filter out "Not detected")
    resume_skills = [
        s.lower() for s in profile.get("skills", []) if s != "Not detected"
    ]

    # Check each target against resume text and skills
    matched = []
    missing = []
    for term in all_targets:
        term_lower = term.lower()
        pattern = r"\b" + re.escape(term_lower) + r"\b"
        in_text = bool(re.search(pattern, resume_lower))
        in_skills = term_lower in resume_skills
        if in_text or in_skills:
            if term not in matched:
                matched.append(term)
        else:
            if term not in missing:
                missing.append(term)

    # Calculate base score from keyword overlap
    total = len(all_targets)
    if total == 0:
        return {
            "target_role": target_role,
            "keywords_entered": target_keywords_raw.strip() or "None",
            "score": 0,
            "level": "Low",
            "matched": [],
            "missing": [],
            "explanation": "No target keywords to match against.",
        }

    base_score = (len(matched) / total) * 80  # max 80 from keyword overlap

    # Bonus points (up to 20) from profile indicators
    bonus = 0
    role_lower = target_role.lower()
    edu_items = profile.get("education", [])
    exp_items = profile.get("experience", [])
    has_edu = any(item != "Not detected" for item in edu_items)
    has_exp = any(item != "Not detected" for item in exp_items)

    if has_edu:
        bonus += 5
    if has_exp:
        bonus += 5
    # Check if role title appears in experience lines
    if any(role_lower in item.lower() for item in exp_items if item != "Not detected"):
        bonus += 10
    elif any(
        word in item.lower()
        for item in exp_items
        if item != "Not detected"
        for word in role_lower.split()
        if len(word) > 3
    ):
        bonus += 5

    score = min(round(base_score + bonus), 100)
    level = _get_level(score)
    explanation = _build_explanation(
        score, level, len(matched), len(missing), target_role
    )

    return {
        "target_role": target_role,
        "keywords_entered": target_keywords_raw.strip() or "None",
        "score": score,
        "level": level,
        "matched": matched,
        "missing": missing,
        "explanation": explanation,
    }


def _parse_keywords(raw):
    """Parse comma-separated keywords into a clean list."""
    if not raw or not raw.strip():
        return []
    parts = [k.strip() for k in raw.split(",") if k.strip()]
    seen = set()
    result = []
    for p in parts:
        if p.lower() not in seen:
            seen.add(p.lower())
            result.append(p)
    return result


def _parse_role_words(role):
    """Extract meaningful words from a role title."""
    stop_words = {"a", "an", "the", "and", "or", "of", "for", "in", "at", "to", "with"}
    words = role.strip().split()
    return [w for w in words if w.lower() not in stop_words and len(w) > 1]


def _get_level(score):
    if score >= 70:
        return "Strong"
    elif score >= 40:
        return "Moderate"
    else:
        return "Low"


def _build_explanation(score, level, matched_count, missing_count, role):
    if level == "Strong":
        return (
            f"Your resume shows strong alignment with the {role} role. "
            f"{matched_count} target term(s) matched."
        )
    elif level == "Moderate":
        msg = (
            f"Your resume has moderate overlap with the {role} role. "
            f"{matched_count} term(s) matched, but {missing_count} target term(s) were not found."
        )
        if missing_count > 0:
            msg += " Consider highlighting those areas in your resume."
        return msg
    else:
        return (
            f"Your resume has limited overlap with the {role} role. "
            f"Only {matched_count} target term(s) matched out of {matched_count + missing_count}. "
            f"Consider adding relevant skills or experience."
        )
