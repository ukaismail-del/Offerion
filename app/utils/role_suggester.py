import re


ROLE_CATALOG = {
    "Software Engineer": {
        "keywords": [
            "python",
            "java",
            "javascript",
            "git",
            "sql",
            "flask",
            "django",
            "api",
            "software",
            "developer",
            "engineering",
            "c++",
            "c#",
            "html",
            "css",
            "linux",
            "docker",
            "agile",
        ],
    },
    "Backend Developer": {
        "keywords": [
            "python",
            "java",
            "sql",
            "flask",
            "django",
            "node.js",
            "api",
            "database",
            "linux",
            "docker",
            "git",
            "server",
            "backend",
        ],
    },
    "Frontend Developer": {
        "keywords": [
            "javascript",
            "typescript",
            "html",
            "css",
            "react",
            "angular",
            "vue",
            "frontend",
            "ui",
            "ux",
            "responsive",
            "git",
        ],
    },
    "Full Stack Developer": {
        "keywords": [
            "python",
            "javascript",
            "html",
            "css",
            "react",
            "node.js",
            "sql",
            "flask",
            "django",
            "git",
            "api",
            "docker",
            "full stack",
        ],
    },
    "Data Analyst": {
        "keywords": [
            "excel",
            "sql",
            "python",
            "data analysis",
            "tableau",
            "power bi",
            "r",
            "statistics",
            "reporting",
            "visualization",
            "analytics",
        ],
    },
    "Data Scientist": {
        "keywords": [
            "python",
            "machine learning",
            "sql",
            "r",
            "data analysis",
            "statistics",
            "tableau",
            "tensorflow",
            "modeling",
            "analytics",
        ],
    },
    "Project Coordinator": {
        "keywords": [
            "project management",
            "communication",
            "excel",
            "coordination",
            "scheduling",
            "agile",
            "scrum",
            "organized",
            "planning",
        ],
    },
    "Project Manager": {
        "keywords": [
            "project management",
            "leadership",
            "communication",
            "agile",
            "scrum",
            "budgeting",
            "planning",
            "stakeholder",
            "strategy",
        ],
    },
    "Marketing Specialist": {
        "keywords": [
            "marketing",
            "sales",
            "communication",
            "social media",
            "seo",
            "content",
            "analytics",
            "campaign",
            "branding",
            "advertising",
        ],
    },
    "Sales Representative": {
        "keywords": [
            "sales",
            "customer service",
            "communication",
            "crm",
            "negotiation",
            "lead",
            "revenue",
            "quota",
            "client",
        ],
    },
    "Financial Analyst": {
        "keywords": [
            "finance",
            "accounting",
            "excel",
            "sql",
            "budgeting",
            "forecasting",
            "financial",
            "analysis",
            "reporting",
            "modeling",
        ],
    },
    "Customer Support Specialist": {
        "keywords": [
            "customer service",
            "communication",
            "support",
            "helpdesk",
            "troubleshooting",
            "ticketing",
            "crm",
            "satisfaction",
        ],
    },
}


def suggest_roles(resume_text, profile):
    """Suggest top roles based on resume text and profile. Returns a list of dicts."""
    resume_lower = resume_text.lower()
    resume_skills = [
        s.lower() for s in profile.get("skills", []) if s != "Not detected"
    ]
    has_edu = any(item != "Not detected" for item in profile.get("education", []))
    has_exp = any(item != "Not detected" for item in profile.get("experience", []))
    exp_lines = [
        item.lower() for item in profile.get("experience", []) if item != "Not detected"
    ]

    scored = []
    for role_name, role_info in ROLE_CATALOG.items():
        keywords = role_info["keywords"]
        matched = []
        for kw in keywords:
            pattern = r"\b" + re.escape(kw) + r"\b"
            in_text = bool(re.search(pattern, resume_lower))
            in_skills = kw in resume_skills
            if in_text or in_skills:
                if kw not in matched:
                    matched.append(kw)

        if not matched:
            continue

        base_score = (len(matched) / len(keywords)) * 80

        bonus = 0
        if has_edu:
            bonus += 3
        if has_exp:
            bonus += 3
        # Check if role name words appear in experience lines
        role_words = [w.lower() for w in role_name.split() if len(w) > 2]
        if any(rw in line for line in exp_lines for rw in role_words):
            bonus += 10
        elif any(kw in line for line in exp_lines for kw in matched[:3]):
            bonus += 4

        score = min(round(base_score + bonus), 100)
        level = _get_level(score)
        reason = _build_reason(role_name, matched, score, level)

        scored.append(
            {
                "role": role_name,
                "score": score,
                "level": level,
                "matched": matched,
                "reason": reason,
            }
        )

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:5]


def _get_level(score):
    if score >= 70:
        return "Strong"
    elif score >= 40:
        return "Moderate"
    else:
        return "Low"


def _build_reason(role, matched, score, level):
    match_count = len(matched)
    top = ", ".join(matched[:4])
    if level == "Strong":
        return f"Strong fit — your resume aligns well with {role} based on {match_count} indicators including {top}."
    elif level == "Moderate":
        return f"Moderate fit — {match_count} relevant indicator(s) found ({top}). Building more experience here could strengthen this path."
    else:
        return f"Some overlap — {match_count} indicator(s) detected ({top}). This role may be worth exploring with additional skills."
