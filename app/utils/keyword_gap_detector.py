"""M31 — Missing Keyword Gap Detector.

Surfaces missing or underrepresented job keywords that could improve fit.
Deterministic — no AI APIs.
"""


def detect_keyword_gaps(match=None, tailored=None, rewrite=None,
                        profile=None):
    """Detect missing and underused keywords.

    Returns a dict with missing_keywords, underused_keywords,
    recommended_additions.  Returns None if no match data.
    """
    if not match:
        return None

    missing = _find_missing(match)
    underused = _find_underused(match, tailored, profile)
    recommended = _build_recommendations(missing, underused, rewrite, tailored)

    return {
        "missing_keywords": missing,
        "underused_keywords": underused,
        "recommended_additions": recommended,
    }


def _find_missing(match):
    """Extract keywords present in target but absent from resume."""
    missing = match.get("missing_keywords", [])
    # Deduplicate and limit
    seen = set()
    result = []
    for kw in missing:
        low = kw.lower().strip()
        if low and low not in seen:
            seen.add(low)
            result.append(kw.strip())
        if len(result) >= 8:
            break
    return result


def _find_underused(match, tailored, profile):
    """Find keywords that appear but may be underrepresented."""
    underused = []
    seen = set()

    # Skills that are matched but not high-priority in tailored
    matched = set(kw.lower() for kw in match.get("matched_keywords", []))

    if tailored and tailored.get("skills_to_feature"):
        for sf in tailored["skills_to_feature"]:
            skill = sf.get("skill", "")
            if (sf.get("priority") in ("medium", "low")
                    and skill.lower() in matched
                    and skill.lower() not in seen):
                underused.append(skill)
                seen.add(skill.lower())

    # Skills in profile but not featured in tailored
    if profile and profile.get("skills") and tailored:
        featured = set()
        if tailored.get("skills_to_feature"):
            featured = {s["skill"].lower() for s in tailored["skills_to_feature"]}
        for sk in profile["skills"]:
            if sk.lower() in matched and sk.lower() not in featured and sk.lower() not in seen:
                underused.append(sk)
                seen.add(sk.lower())

    return underused[:6]


def _build_recommendations(missing, underused, rewrite, tailored):
    """Build actionable keyword addition recommendations."""
    recs = []
    seen = set()

    # From rewrite keyword_additions
    if rewrite and rewrite.get("keyword_additions"):
        for kw in rewrite["keyword_additions"]:
            low = kw.lower().strip()
            if low not in seen:
                recs.append(f"Add \"{kw}\" to your skills or experience section")
                seen.add(low)

    # From missing keywords
    for kw in missing[:3]:
        low = kw.lower()
        if low not in seen:
            recs.append(f"Include \"{kw}\" in relevant resume sections")
            seen.add(low)

    # From underused
    for kw in underused[:2]:
        low = kw.lower()
        if low not in seen:
            recs.append(f"Strengthen mention of \"{kw}\" with context or examples")
            seen.add(low)

    if not recs:
        recs.append("No critical keyword gaps detected at this stage")

    return recs[:8]
