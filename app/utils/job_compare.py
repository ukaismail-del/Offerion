import re

# Starter keyword library for job description analysis
JD_KEYWORDS = [
    "python",
    "sql",
    "flask",
    "django",
    "javascript",
    "typescript",
    "react",
    "angular",
    "vue",
    "node.js",
    "html",
    "css",
    "apis",
    "rest",
    "graphql",
    "git",
    "docker",
    "kubernetes",
    "aws",
    "azure",
    "gcp",
    "linux",
    "excel",
    "power bi",
    "tableau",
    "data analysis",
    "data science",
    "machine learning",
    "deep learning",
    "nlp",
    "statistics",
    "leadership",
    "communication",
    "project management",
    "agile",
    "scrum",
    "marketing",
    "sales",
    "finance",
    "customer service",
    "accounting",
    "java",
    "c++",
    "c#",
    "go",
    "rust",
    "ruby",
    "php",
    "swift",
    "kotlin",
    "tensorflow",
    "pytorch",
    "pandas",
    "numpy",
    "spark",
    "hadoop",
    "mongodb",
    "postgresql",
    "mysql",
    "redis",
    "elasticsearch",
    "ci/cd",
    "jenkins",
    "terraform",
    "ansible",
    "figma",
    "photoshop",
    "illustrator",
    "ui/ux",
    "seo",
    "google analytics",
    "crm",
    "salesforce",
    "hubspot",
    "jira",
    "confluence",
    "slack",
    "trello",
    "problem solving",
    "teamwork",
    "time management",
    "critical thinking",
    "negotiation",
    "presentation",
    "writing",
    "research",
    "supply chain",
    "logistics",
    "operations",
    "quality assurance",
    "testing",
    "automation",
    "security",
    "networking",
]


def _normalize(text):
    """Lowercase and collapse whitespace."""
    return re.sub(r"\s+", " ", text.lower().strip())


def extract_jd_keywords(jd_text):
    """Extract known keywords found in the job description text."""
    normalized = _normalize(jd_text)
    found = []
    for kw in JD_KEYWORDS:
        if kw in normalized:
            found.append(kw)
    return sorted(set(found))


def compare_resume_to_jd(resume_text, profile, jd_text):
    """Compare a resume against a pasted job description.

    Returns a dict with:
        jd_keywords, matched, missing, score, level, explanation
    """
    jd_keywords = extract_jd_keywords(jd_text)

    if not jd_keywords:
        return {
            "jd_keywords": [],
            "matched": [],
            "missing": [],
            "score": 0,
            "level": "Low",
            "explanation": (
                "No recognizable keywords were found in the job description. "
                "Try pasting a more detailed listing."
            ),
        }

    resume_normalized = _normalize(resume_text)

    # Also pull in detected skills from the profile
    profile_skills = {
        s.lower() for s in profile.get("skills", []) if s != "Not detected"
    }

    matched = []
    missing = []

    for kw in jd_keywords:
        if kw in resume_normalized or kw in profile_skills:
            matched.append(kw)
        else:
            missing.append(kw)

    total = len(jd_keywords)
    score = round((len(matched) / total) * 100) if total > 0 else 0

    if score >= 70:
        level = "Strong"
    elif score >= 40:
        level = "Moderate"
    else:
        level = "Low"

    explanation = _build_explanation(matched, missing, score, level, total)

    return {
        "jd_keywords": jd_keywords,
        "matched": matched,
        "missing": missing,
        "score": score,
        "level": level,
        "explanation": explanation,
    }


def _build_explanation(matched, missing, score, level, total):
    """Build a human-readable explanation of the comparison."""
    parts = []
    parts.append(
        f"Your resume matches {len(matched)} of {total} keywords "
        f"found in the job description ({score}%)."
    )

    if level == "Strong":
        parts.append(
            "Strong overlap — your resume aligns well with this job description."
        )
    elif level == "Moderate":
        parts.append(
            "Moderate overlap — there are gaps you could address to strengthen your fit."
        )
    else:
        parts.append(
            "Low overlap — consider tailoring your resume significantly for this role."
        )

    if missing:
        top_missing = ", ".join(missing[:5])
        parts.append(f"Key missing terms: {top_missing}.")

    return " ".join(parts)
