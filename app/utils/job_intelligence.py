"""M93 — Job Description Intelligence Extractor.

Derives structured intelligence from a job payload using
title + description text.  Deterministic — no external NLP.
"""

from app.utils.job_sources import extract_skills_from_text

# ── seniority tokens ─────────────────────────────────────────────
_SENIORITY_TOKENS = [
    ("principal", "Principal"),
    ("staff", "Staff"),
    ("lead", "Lead"),
    ("senior", "Senior"),
    ("manager", "Manager"),
    ("director", "Director"),
    ("vp", "VP"),
    ("head of", "Head"),
    ("mid-level", "Mid-Level"),
    ("mid level", "Mid-Level"),
    ("associate", "Associate"),
    ("junior", "Junior"),
    ("entry-level", "Entry-Level"),
    ("entry level", "Entry-Level"),
    ("intern", "Intern"),
]

# ── domain hint tokens ───────────────────────────────────────────
_DOMAIN_TOKENS = [
    ("backend", "Backend"),
    ("front-end", "Frontend"),
    ("frontend", "Frontend"),
    ("full-stack", "Full-Stack"),
    ("fullstack", "Full-Stack"),
    ("devops", "DevOps"),
    ("data engineer", "Data Engineering"),
    ("data scientist", "Data Science"),
    ("data anal", "Data & Analytics"),
    ("machine learning", "Machine Learning"),
    ("ml engineer", "Machine Learning"),
    ("mobile", "Mobile"),
    ("ios", "Mobile"),
    ("android", "Mobile"),
    ("cloud", "Cloud & Infrastructure"),
    ("infrastructure", "Cloud & Infrastructure"),
    ("security", "Security"),
    ("cybersecurity", "Security"),
    ("marketing", "Marketing"),
    ("digital marketing", "Marketing"),
    ("growth", "Marketing"),
    ("seo", "Marketing"),
    ("product manag", "Product"),
    ("product owner", "Product"),
    ("product strategy", "Product"),
    ("design", "Design"),
    ("ux", "Design"),
    ("ui", "Design"),
    ("operations", "Operations"),
    ("supply chain", "Operations"),
    ("sales", "Sales"),
    ("account executive", "Sales"),
    ("business develop", "Sales"),
    ("hr", "Human Resources"),
    ("recruiting", "Human Resources"),
    ("talent", "Human Resources"),
    ("finance", "Finance"),
    ("financial", "Finance"),
    ("accounting", "Finance"),
    ("qa", "Quality Assurance"),
    ("quality assurance", "Quality Assurance"),
    ("testing", "Quality Assurance"),
    ("technical writ", "Technical Writing"),
    ("content", "Content"),
    ("editorial", "Content"),
]

# ── responsibility signal phrases ─────────────────────────────────
_RESPONSIBILITY_SIGNALS = [
    "build and maintain",
    "design and implement",
    "collaborate with",
    "lead a team",
    "manage a team",
    "own the",
    "drive",
    "mentor",
    "optimize",
    "architect",
    "deliver",
    "scale",
    "automate",
    "analyze",
    "report to",
    "work closely with",
    "develop and deploy",
    "troubleshoot",
    "improve",
    "define strategy",
    "present to stakeholders",
    "manage stakeholders",
    "cross-functional",
]

# ── required / preferred heuristic tokens ─────────────────────────
_REQUIRED_PREFIXES = [
    "must have",
    "required",
    "requirements",
    "minimum qualifications",
    "you have",
    "you bring",
    "strong experience in",
    "proficiency in",
    "proven experience",
    "deep knowledge",
]

_PREFERRED_PREFIXES = [
    "nice to have",
    "preferred",
    "bonus",
    "ideally",
    "a plus",
    "nice-to-have",
    "desirable",
    "familiarity with",
    "exposure to",
]


def extract_job_intelligence(job):
    """Derive structured intelligence from a job payload.

    Parameters
    ----------
    job : dict
        Must contain at least ``title``.  ``description`` is used when
        available for deeper extraction.

    Returns
    -------
    dict with keys: keywords, required_skills, preferred_skills,
    seniority_hint, domain_hint, responsibility_signals.
    """
    title = (job.get("title") or "").strip()
    description = (job.get("description") or "").strip()
    text = f"{title} {description}"
    lower = text.lower()

    # ── keywords: all extracted skills from text ──────────────────
    keywords = extract_skills_from_text(text)

    # ── required vs preferred classification ──────────────────────
    required_skills, preferred_skills = _classify_skills(
        keywords, description, job.get("skills", [])
    )

    # ── seniority hint (check title first, most reliable) ────────
    seniority_hint = _detect_seniority(title.lower()) or _detect_seniority(lower)

    # ── domain hint ───────────────────────────────────────────────
    domain_hint = _detect_domain(lower)

    # ── responsibility signals ────────────────────────────────────
    responsibilities = _detect_responsibilities(lower)

    return {
        "keywords": keywords,
        "required_skills": required_skills,
        "preferred_skills": preferred_skills,
        "seniority_hint": seniority_hint,
        "domain_hint": domain_hint,
        "responsibility_signals": responsibilities,
    }


def _classify_skills(keywords, description, explicit_skills):
    """Split skills into required and preferred buckets.

    Heuristic: if the description contains contextual cues near a skill
    mention, classify it accordingly.  Skills listed explicitly in the
    job's skills array are treated as required.  Remaining extracted
    keywords default to required unless a preferred cue is found nearby.
    """
    desc_lower = description.lower() if description else ""
    explicit_lower = {s.lower() for s in (explicit_skills or [])}

    required = []
    preferred = []

    for skill in keywords:
        # Explicit job skills are always required
        if skill in explicit_lower:
            required.append(skill)
        elif _near_cue(desc_lower, skill, _PREFERRED_PREFIXES):
            preferred.append(skill)
        else:
            required.append(skill)

    return sorted(set(required)), sorted(set(preferred))


def _near_cue(text, skill, cues, window=80):
    """Check if any cue phrase appears within *window* chars of *skill*."""
    pos = text.find(skill)
    if pos < 0:
        return False
    start = max(0, pos - window)
    end = min(len(text), pos + len(skill) + window)
    snippet = text[start:end]
    return any(c in snippet for c in cues)


def _detect_seniority(lower_text):
    """Return the first matching seniority hint or None."""
    for token, label in _SENIORITY_TOKENS:
        if token in lower_text:
            return label
    return None


def _detect_domain(lower_text):
    """Return the first matching domain hint or None."""
    for token, label in _DOMAIN_TOKENS:
        if token in lower_text:
            return label
    return None


def _detect_responsibilities(lower_text):
    """Return matching responsibility signal phrases found in text."""
    found = []
    for signal in _RESPONSIBILITY_SIGNALS:
        if signal in lower_text:
            found.append(signal)
    return found
