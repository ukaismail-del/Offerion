def generate_scorecard(resume_text, profile, match=None, jd_comparison=None):
    """Generate a resume strength scorecard with category scores.

    Returns a dict with scores, labels, and highlights.
    Returns None if profile is not available.
    """
    if not profile:
        return None

    text_length = len(resume_text.strip())
    has_name = profile.get("name", "Not detected") != "Not detected"
    has_email = profile.get("email", "Not detected") != "Not detected"
    has_phone = profile.get("phone", "Not detected") != "Not detected"
    skills = [s for s in profile.get("skills", []) if s != "Not detected"]
    edu_items = [e for e in profile.get("education", []) if e != "Not detected"]
    exp_items = [e for e in profile.get("experience", []) if e != "Not detected"]

    contact_score = _score_contact(has_name, has_email, has_phone)
    skills_score = _score_skills(skills)
    experience_score = _score_experience(exp_items, text_length)
    education_score = _score_education(edu_items)
    ats_score = _score_ats(match, jd_comparison, skills)
    overall_score = _score_overall(
        contact_score, skills_score, experience_score, education_score, ats_score
    )

    scores = {
        "contact_info": contact_score,
        "skills_coverage": skills_score,
        "experience_strength": experience_score,
        "education_completeness": education_score,
        "ats_alignment": ats_score,
        "overall": overall_score,
    }

    labels = {k: _label(v) for k, v in scores.items()}

    highlights = _build_highlights(scores, labels, match, jd_comparison)

    return {
        "scores": scores,
        "labels": labels,
        "highlights": highlights,
    }


def _score_contact(has_name, has_email, has_phone):
    score = 0
    if has_name:
        score += 35
    if has_email:
        score += 35
    if has_phone:
        score += 30
    return score


def _score_skills(skills):
    count = len(skills)
    if count == 0:
        return 0
    if count == 1:
        return 15
    if count == 2:
        return 30
    if count <= 4:
        return 50
    if count <= 7:
        return 70
    if count <= 10:
        return 85
    return 100


def _score_experience(exp_items, text_length):
    score = 0
    count = len(exp_items)
    if count >= 5:
        score += 60
    elif count >= 3:
        score += 45
    elif count >= 1:
        score += 25

    # Bonus for text richness
    if text_length >= 1500:
        score += 40
    elif text_length >= 800:
        score += 30
    elif text_length >= 400:
        score += 20
    elif text_length >= 200:
        score += 10

    return min(score, 100)


def _score_education(edu_items):
    count = len(edu_items)
    if count == 0:
        return 0
    if count == 1:
        return 50
    if count == 2:
        return 75
    return 100


def _score_ats(match, jd_comparison, skills):
    components = []

    if match:
        components.append(match.get("score", 0))
    if jd_comparison:
        components.append(jd_comparison.get("score", 0))

    if not components:
        # No target data — base ATS on skills count alone
        if len(skills) >= 8:
            return 65
        elif len(skills) >= 4:
            return 45
        elif len(skills) >= 1:
            return 25
        return 10

    return round(sum(components) / len(components))


def _score_overall(contact, skills, experience, education, ats):
    # Weighted average: experience and skills matter most
    weighted = (
        contact * 0.10
        + skills * 0.25
        + experience * 0.30
        + education * 0.10
        + ats * 0.25
    )
    return round(weighted)


def _label(score):
    if score >= 80:
        return "Strong"
    if score >= 60:
        return "Good"
    if score >= 40:
        return "Fair"
    return "Weak"


CATEGORY_DISPLAY = {
    "contact_info": "Contact Info",
    "skills_coverage": "Skills Coverage",
    "experience_strength": "Experience Strength",
    "education_completeness": "Education Completeness",
    "ats_alignment": "ATS Alignment",
    "overall": "Overall Resume Strength",
}


def _build_highlights(scores, labels, match, jd_comparison):
    highlights = []

    overall = scores["overall"]
    if overall >= 80:
        highlights.append(
            f"Your overall resume strength is {overall}/100 — looking strong."
        )
    elif overall >= 60:
        highlights.append(
            f"Overall score: {overall}/100. A few targeted improvements could push this higher."
        )
    elif overall >= 40:
        highlights.append(
            f"Overall score: {overall}/100. Several areas need attention."
        )
    else:
        highlights.append(
            f"Overall score: {overall}/100. Significant work is needed across multiple sections."
        )

    # Highlight weakest category (excluding overall)
    category_scores = {
        k: v for k, v in scores.items() if k != "overall"
    }
    weakest = min(category_scores, key=category_scores.get)
    weakest_score = category_scores[weakest]
    if weakest_score < 60:
        highlights.append(
            f"Weakest area: {CATEGORY_DISPLAY[weakest]} ({weakest_score}/100). "
            f"Focus your improvements here."
        )

    # Highlight strongest category
    strongest = max(category_scores, key=category_scores.get)
    strongest_score = category_scores[strongest]
    if strongest_score >= 70:
        highlights.append(
            f"Strongest area: {CATEGORY_DISPLAY[strongest]} ({strongest_score}/100)."
        )

    if match and match.get("score", 0) >= 70:
        highlights.append("Strong target-role alignment boosts your ATS score.")
    elif jd_comparison and jd_comparison.get("score", 0) >= 70:
        highlights.append("Good job description overlap — your ATS score benefits.")

    if scores["skills_coverage"] < 50:
        highlights.append(
            "Adding more skills to your resume would improve multiple scores."
        )

    return highlights
