import re


SKILLS_LIST = [
    "Python",
    "Flask",
    "Django",
    "SQL",
    "Excel",
    "JavaScript",
    "TypeScript",
    "HTML",
    "CSS",
    "React",
    "Angular",
    "Vue",
    "Node.js",
    "Git",
    "Docker",
    "AWS",
    "Azure",
    "Linux",
    "Java",
    "C++",
    "C#",
    "R",
    "Tableau",
    "Power BI",
    "Data Analysis",
    "Machine Learning",
    "Project Management",
    "Communication",
    "Leadership",
    "Customer Service",
    "Sales",
    "Marketing",
    "Finance",
    "Accounting",
    "Agile",
    "Scrum",
]

EDUCATION_KEYWORDS = [
    "bachelor",
    "master",
    "mba",
    "ph.d",
    "phd",
    "associate",
    "diploma",
    "b.s.",
    "b.a.",
    "m.s.",
    "m.a.",
    "b.sc",
    "m.sc",
    "degree",
    "university",
    "college",
    "institute",
    "school of",
    "computer science",
    "engineering",
    "business administration",
]

EXPERIENCE_KEYWORDS = [
    "experience",
    "worked at",
    "employed",
    "position",
    "role",
    "responsible for",
    "managed",
    "developed",
    "led",
    "created",
    "intern",
    "internship",
    "coordinator",
    "analyst",
    "engineer",
    "manager",
    "director",
    "supervisor",
    "consultant",
    "specialist",
]


def analyze_resume(text):
    """Analyze extracted resume text and return a structured profile dict."""
    return {
        "name": _detect_name(text),
        "email": _detect_email(text),
        "phone": _detect_phone(text),
        "skills": _detect_skills(text),
        "education": _detect_education(text),
        "experience": _detect_experience(text),
    }


def _detect_email(text):
    match = re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text)
    return match.group(0) if match else "Not detected"


def _detect_phone(text):
    match = re.search(r"(\+?1[\s.\-]?)?\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}", text)
    return match.group(0).strip() if match else "Not detected"


def _detect_name(text):
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    for line in lines[:5]:
        # Skip lines that look like emails, phones, URLs, or long sentences
        if "@" in line or re.search(r"\d{3}[\s.\-]?\d{3}", line):
            continue
        if line.startswith("http") or len(line) > 60:
            continue
        # A likely name line: short, mostly letters, 2-4 words
        words = line.split()
        if 2 <= len(words) <= 4 and all(w.isalpha() for w in words):
            return line
    return "Not detected"


def _detect_skills(text):
    text_lower = text.lower()
    found = []
    for skill in SKILLS_LIST:
        pattern = r"\b" + re.escape(skill.lower()) + r"\b"
        if re.search(pattern, text_lower):
            if skill not in found:
                found.append(skill)
    return found if found else ["Not detected"]


def _detect_education(text):
    lines = text.split("\n")
    hints = []
    for line in lines:
        line_lower = line.lower().strip()
        if not line_lower:
            continue
        for kw in EDUCATION_KEYWORDS:
            if kw in line_lower and line.strip() not in hints:
                hints.append(line.strip())
                break
    return hints[:5] if hints else ["Not detected"]


def _detect_experience(text):
    lines = text.split("\n")
    hints = []
    for line in lines:
        line_lower = line.lower().strip()
        if not line_lower:
            continue
        # Match lines with year patterns like 2018-2021 or 2020 - Present
        has_year = bool(re.search(r"\b20\d{2}\b", line_lower))
        has_keyword = any(kw in line_lower for kw in EXPERIENCE_KEYWORDS)
        if (has_year or has_keyword) and line.strip() not in hints:
            hints.append(line.strip())
    return hints[:6] if hints else ["Not detected"]
