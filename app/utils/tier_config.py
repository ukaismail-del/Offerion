"""M54 — Tier System Foundation.

Defines the five-tier access hierarchy and provides the ``has_access``
helper used by routes and templates to gate features.

Tiers (lowest → highest):
  free → comet → operator → professional → elite
"""

# Ordered from lowest to highest privilege
TIER_ORDER = ["free", "comet", "operator", "professional", "elite"]

# Minimum tier required for each feature key
FEATURE_TIERS = {
    # Resume basics — free
    "resume_analysis": "free",
    "resume_preview": "free",
    "download_resume_draft": "free",
    # Enhancement — comet+
    "enhance_resume": "comet",
    "save_version": "comet",
    # Cover letter — comet (generate), operator (enhance)
    "generate_cover_letter": "comet",
    "enhance_cover_letter": "operator",
    # Application packages — operator+
    "save_package": "operator",
    "download_package": "operator",
    # Job tracker — operator+
    "save_job": "operator",
    "job_detail": "operator",
    "job_status": "operator",
    "delete_job": "operator",
    # Alerts — professional+
    "create_alert": "professional",
    "complete_alert": "professional",
    "delete_alert": "professional",
    # Guided flow — operator+
    "prepare_application": "operator",
}

# Human-readable tier metadata for the pricing page
TIER_CONFIG = {
    "free": {
        "label": "Free",
        "price": "$0",
        "tagline": "Get started",
        "features": [
            "Resume analysis & scoring",
            "Basic resume preview",
            "Download resume draft",
        ],
    },
    "comet": {
        "label": "Comet",
        "price": "$9/mo",
        "tagline": "Turn your resume into an interview-ready asset",
        "features": [
            "Everything in Free",
            "AI resume enhancement",
            "Save resume versions",
            "Generate cover letter",
        ],
    },
    "operator": {
        "label": "Operator",
        "price": "$19/mo",
        "tagline": "Generate complete job applications in one click",
        "features": [
            "Everything in Comet",
            "Cover letter enhancement",
            "Application packages",
            "Job tracker (save & manage)",
            "One-click application prep",
        ],
    },
    "professional": {
        "label": "Professional",
        "price": "$29/mo",
        "tagline": "Never miss a follow-up again",
        "features": [
            "Everything in Operator",
            "Follow-up alerts",
            "Full workflow automation",
        ],
    },
    "elite": {
        "label": "Elite",
        "price": "$49/mo",
        "tagline": "Operate at peak job search efficiency",
        "features": [
            "Everything in Professional",
            "Priority processing",
            "Early access to new features",
        ],
    },
}

# Version limits per tier (0 = unlimited)
TIER_LIMITS = {
    "free": {"resume_versions": 2, "packages": 0, "saved_jobs": 0},
    "comet": {"resume_versions": 5, "packages": 0, "saved_jobs": 0},
    "operator": {"resume_versions": 15, "packages": 10, "saved_jobs": 10},
    "professional": {"resume_versions": 0, "packages": 0, "saved_jobs": 0},
    "elite": {"resume_versions": 0, "packages": 0, "saved_jobs": 0},
}


def _tier_rank(tier_name):
    """Return numeric rank for a tier (0 = free)."""
    try:
        return TIER_ORDER.index(tier_name)
    except ValueError:
        return 0


def has_access(user_tier, feature_key):
    """Return True if *user_tier* meets the minimum for *feature_key*."""
    required = FEATURE_TIERS.get(feature_key)
    if required is None:
        return True  # undefined feature → allow
    return _tier_rank(user_tier) >= _tier_rank(required)


def required_tier_for(feature_key):
    """Return the minimum tier name needed for *feature_key*."""
    return FEATURE_TIERS.get(feature_key, "free")


def tier_label(tier_name):
    """Return the human-readable label for a tier."""
    cfg = TIER_CONFIG.get(tier_name)
    return cfg["label"] if cfg else tier_name.title()


def check_limit(user_tier, limit_key, current_count):
    """Return True if the user is within quota for *limit_key*."""
    limits = TIER_LIMITS.get(user_tier, TIER_LIMITS["free"])
    cap = limits.get(limit_key, 0)
    if cap == 0:
        return True  # unlimited
    return current_count < cap
