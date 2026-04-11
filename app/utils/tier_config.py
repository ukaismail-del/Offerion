"""M54 — Tier System Foundation.

Defines the five-tier access hierarchy and provides the ``has_access``
helper used by routes and templates to gate features.

Tiers (lowest → highest):
  free → comet → operator → professional → elite → trial
"""

from datetime import datetime, timedelta

# Ordered from lowest to highest privilege
TIER_ORDER = ["free", "comet", "operator", "professional", "elite", "trial"]

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
        "tagline": "Get started with basic resume analysis",
        "features": [
            "3\u20135 job matches per day",
            "Basic resume analysis",
            "Preview-only outputs",
        ],
    },
    "comet": {
        "label": "Comet",
        "price": "$19/mo",
        "tagline": "Turn your resume into an interview-ready asset",
        "features": [
            "Everything in Free",
            "AI resume enhancement",
            "Cover letter generation",
            "Save & manage versions",
        ],
    },
    "operator": {
        "label": "Operator",
        "price": "$39/mo",
        "tagline": "Turn your resume into targeted applications in minutes",
        "features": [
            "Everything in Comet",
            "Full job matching engine",
            "Job tracker (save/manage jobs)",
            "Application packages",
            "One-click application prep",
        ],
    },
    "professional": {
        "label": "Professional",
        "price": "$59/mo",
        "tagline": "Never miss a follow-up again",
        "features": [
            "Everything in Operator",
            "Follow-up alerts",
            "Workflow automation",
            "Priority processing",
        ],
    },
    "elite": {
        "label": "Elite",
        "price": "$59/mo",
        "tagline": "Full access",
        "features": [
            "Everything in Professional",
            "Priority processing",
            "Early access to new features",
        ],
    },
    "trial": {
        "label": "Trial",
        "price": "Free for 7 days",
        "tagline": "Full access — all features unlocked",
        "features": [
            "Everything in Elite",
            "All features unlocked for 7 days",
            "No credit card required",
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
    "trial": {"resume_versions": 0, "packages": 0, "saved_jobs": 0},
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


# ------------------------------------------------------------------
# Trial helpers
# ------------------------------------------------------------------

TRIAL_DURATION_DAYS = 7


def start_trial(user):
    """Activate a 7-day trial on a UserIdentity instance."""
    user.tier = "trial"
    user.trial_start = datetime.utcnow()
    user.trial_end = datetime.utcnow() + timedelta(days=TRIAL_DURATION_DAYS)
    user.daily_matches_used = 0
    user.last_usage_reset = user.trial_start


def check_trial_expiry(user):
    """If trial has expired, downgrade to free. Returns current tier."""
    if user.tier == "trial" and user.trial_end:
        if datetime.utcnow() > user.trial_end:
            user.tier = "free"
    return user.tier


def trial_days_remaining(user):
    """Return days left in trial, or None if not on trial."""
    if user.tier != "trial" or not user.trial_end:
        return None
    delta = (user.trial_end - datetime.utcnow()).days
    return max(delta, 0)


def reset_daily_usage(user):
    """Reset daily usage counter if a new day has started."""
    if not user.last_usage_reset:
        user.daily_matches_used = 0
        user.last_usage_reset = datetime.utcnow()
        return
    if (datetime.utcnow() - user.last_usage_reset).days >= 1:
        user.daily_matches_used = 0
        user.last_usage_reset = datetime.utcnow()


def can_use_job_match(user):
    """Check if the user can perform a job match (free users limited to 5/day)."""
    tier = check_trial_expiry(user)
    if tier in ("operator", "professional", "elite", "trial"):
        return True
    reset_daily_usage(user)
    if user.daily_matches_used >= 5:
        return False
    user.daily_matches_used += 1
    return True
