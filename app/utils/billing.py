"""Bundle W — Plan Enforcement & Usage Tracking.

Central helper for runtime plan rules.  All route-level enforcement
should call functions here rather than scattering if-statements.

Plan states (normalised):
  free   — limited access, upgrade prompts
  trial  — 7 days, generous limits, full feature access
  paid   — unlimited (any tier >= comet that has been purchased)
"""

from datetime import datetime, timedelta

PAID_ACCESS_STATUSES = {"active", "trialing"}
FALLBACK_TO_FREE_STATUSES = {"canceled", "incomplete_expired", "unpaid", "past_due"}
BILLING_ISSUE_STATUSES = {"past_due", "incomplete", "unpaid"}

# ── Limits ────────────────────────────────────────────────────────

FREE_RESUME_ANALYSES = 2  # per month
FREE_JOB_VIEWS = 10  # per month
FREE_REPORT_DOWNLOADS = 1  # per month
FREE_RESUME_DOWNLOADS = 0  # blocked entirely

TRIAL_RESUME_ANALYSES = 10  # during entire trial
TRIAL_JOB_VIEWS = 50  # during entire trial

# ── Plan state helpers ────────────────────────────────────────────


def get_user_plan_state(user):
    """Return normalised plan state: 'free', 'trial', or 'paid'.

    ``paid`` means the user's ``subscription_status`` is 'active'.
    ``trial`` means still within the trial window.
    Otherwise ``free``.
    """
    if not user:
        return "free"
    if (
        normalize_subscription_status(getattr(user, "subscription_status", None))
        in PAID_ACCESS_STATUSES
    ):
        return "paid"
    tier = getattr(user, "tier", "free") or "free"
    if tier == "trial":
        if _is_trial_active(user):
            return "trial"
        return "free"
    # Preserved tiers like comet/operator/etc without active subscription
    # are treated as free for enforcement purposes in this bundle
    return "free"


def _is_trial_active(user):
    """True when user is on trial and it hasn't expired."""
    if not user:
        return False
    trial_end = getattr(user, "trial_end", None)
    if not trial_end:
        return False
    return datetime.utcnow() <= trial_end


def is_trial_active(user):
    """Public wrapper."""
    return _is_trial_active(user) and (getattr(user, "tier", "") == "trial")


def normalize_subscription_status(status):
    """Normalize Stripe subscription status values to lowercase strings."""
    if not status:
        return None
    return str(status).strip().lower()


def subscription_has_paid_access(status):
    """Return True when a Stripe status should keep paid entitlements active."""
    return normalize_subscription_status(status) in PAID_ACCESS_STATUSES


def apply_subscription_state(
    user,
    status,
    tier_name=None,
    subscription_id=None,
    customer_id=None,
    price_id=None,
    current_period_end=None,
    cancel_at_period_end=False,
    now=None,
):
    """Apply a Stripe lifecycle update to the user consistently."""
    if not user:
        return None

    now = now or datetime.utcnow()
    normalized_status = normalize_subscription_status(status)

    if customer_id:
        user.stripe_customer_id = customer_id
    if subscription_id:
        user.stripe_subscription_id = subscription_id
    if price_id:
        user.stripe_price_id = price_id

    user.subscription_status = normalized_status
    user.subscription_updated_at = now
    user.subscription_current_period_end = current_period_end
    user.cancel_at_period_end = bool(cancel_at_period_end)

    if subscription_has_paid_access(normalized_status):
        if tier_name and tier_name not in ("free", "trial"):
            user.tier = tier_name
        user.paid_started_at = user.paid_started_at or now
        user.subscription_canceled_at = None
        user.billing_issue_at = None
    elif normalized_status in BILLING_ISSUE_STATUSES:
        user.billing_issue_at = now
        user.cancel_at_period_end = False
        user.tier = "free"
    elif normalized_status in FALLBACK_TO_FREE_STATUSES:
        user.tier = "free"
        user.subscription_canceled_at = now
        if normalized_status != "past_due":
            user.billing_issue_at = None
        if normalized_status == "canceled":
            user.cancel_at_period_end = False

    return normalized_status


# ── Monthly reset ─────────────────────────────────────────────────


def should_reset_monthly_usage(user, now=None):
    """True if usage counters should be reset (new calendar month)."""
    if not user:
        return False
    reset_at = getattr(user, "usage_reset_at", None)
    if not reset_at:
        return True  # never reset → do it now
    now = now or datetime.utcnow()
    return (now.year, now.month) != (reset_at.year, reset_at.month)


def reset_monthly_usage_if_needed(user, now=None):
    """Reset counters if a new month has begun.  Mutates the user in place."""
    if not user:
        return
    now = now or datetime.utcnow()
    if should_reset_monthly_usage(user, now):
        user.monthly_resume_analyses_used = 0
        user.monthly_job_views_used = 0
        user.monthly_resume_downloads_used = 0
        user.usage_reset_at = now


# ── Access checks ─────────────────────────────────────────────────


def can_run_resume_analysis(user):
    """Return True if the user may run another resume analysis."""
    plan = get_user_plan_state(user)
    if plan == "paid":
        return True
    reset_monthly_usage_if_needed(user)
    used = getattr(user, "monthly_resume_analyses_used", 0)
    if plan == "trial":
        return used < TRIAL_RESUME_ANALYSES
    return used < FREE_RESUME_ANALYSES


def can_view_jobs(user):
    """Return True if the user may view more recommended jobs."""
    plan = get_user_plan_state(user)
    if plan == "paid":
        return True
    reset_monthly_usage_if_needed(user)
    used = getattr(user, "monthly_job_views_used", 0)
    if plan == "trial":
        return used < TRIAL_JOB_VIEWS
    return used < FREE_JOB_VIEWS


def can_download_tailored_resume(user):
    """Tailored resume download: trial + paid only."""
    plan = get_user_plan_state(user)
    return plan in ("trial", "paid")


def can_download_report(user):
    """Report download: free gets 1/month, trial/paid unlimited."""
    plan = get_user_plan_state(user)
    if plan in ("trial", "paid"):
        return True
    reset_monthly_usage_if_needed(user)
    used = getattr(user, "monthly_resume_downloads_used", 0)
    return used < FREE_REPORT_DOWNLOADS


# ── Usage recording ───────────────────────────────────────────────


def record_resume_analysis_usage(user):
    """Increment the resume analysis counter."""
    if not user:
        return
    reset_monthly_usage_if_needed(user)
    user.monthly_resume_analyses_used = (
        getattr(user, "monthly_resume_analyses_used", 0) + 1
    )


def record_job_view_usage(user, count=1):
    """Increment job view counter by *count* (number of jobs displayed)."""
    if not user:
        return
    reset_monthly_usage_if_needed(user)
    user.monthly_job_views_used = getattr(user, "monthly_job_views_used", 0) + count


def record_resume_download_usage(user):
    """Increment the report/resume download counter."""
    if not user:
        return
    reset_monthly_usage_if_needed(user)
    user.monthly_resume_downloads_used = (
        getattr(user, "monthly_resume_downloads_used", 0) + 1
    )


# ── Upgrade reason ────────────────────────────────────────────────

_ACTION_LABELS = {
    "resume_analysis": "resume analyses",
    "job_views": "recommended job views",
    "tailored_resume": "tailored resume downloads",
    "report": "report downloads",
}


def get_upgrade_reason(user, action):
    """Return a user-friendly upgrade message, or None if allowed."""
    plan = get_user_plan_state(user)
    if plan == "paid":
        return None

    checkers = {
        "resume_analysis": can_run_resume_analysis,
        "job_views": can_view_jobs,
        "tailored_resume": can_download_tailored_resume,
        "report": can_download_report,
    }
    checker = checkers.get(action)
    if checker and checker(user):
        return None

    label = _ACTION_LABELS.get(action, action)
    if plan == "trial":
        return f"You\u2019ve reached your trial limit for {label}. Upgrade to continue."
    return f"You\u2019ve reached the free limit for {label}. Upgrade for more."


# ── Remaining counters (for UI) ───────────────────────────────────


def get_usage_summary(user):
    """Return dict with remaining/used counters for the billing card."""
    plan = get_user_plan_state(user)
    reset_monthly_usage_if_needed(user)

    analyses_used = getattr(user, "monthly_resume_analyses_used", 0)
    jobs_used = getattr(user, "monthly_job_views_used", 0)
    downloads_used = getattr(user, "monthly_resume_downloads_used", 0)
    current_period_end = getattr(user, "subscription_current_period_end", None)
    current_period_end_label = (
        current_period_end.strftime("%Y-%m-%d") if current_period_end else None
    )

    if plan == "paid":
        return {
            "plan": "paid",
            "subscription_status": normalize_subscription_status(
                getattr(user, "subscription_status", None)
            ),
            "cancel_at_period_end": bool(getattr(user, "cancel_at_period_end", False)),
            "current_period_end": current_period_end,
            "current_period_end_label": current_period_end_label,
            "billing_issue": bool(getattr(user, "billing_issue_at", None)),
            "analyses_used": analyses_used,
            "analyses_limit": None,  # unlimited
            "analyses_left": None,
            "jobs_used": jobs_used,
            "jobs_limit": None,
            "jobs_left": None,
            "downloads_used": downloads_used,
            "downloads_limit": None,
            "downloads_left": None,
            "can_download_tailored": True,
        }

    if plan == "trial":
        a_limit = TRIAL_RESUME_ANALYSES
        j_limit = TRIAL_JOB_VIEWS
        d_limit = None  # unlimited during trial
    else:
        a_limit = FREE_RESUME_ANALYSES
        j_limit = FREE_JOB_VIEWS
        d_limit = FREE_REPORT_DOWNLOADS

    return {
        "plan": plan,
        "subscription_status": (
            normalize_subscription_status(getattr(user, "subscription_status", None))
            if user
            else None
        ),
        "cancel_at_period_end": (
            bool(getattr(user, "cancel_at_period_end", False)) if user else False
        ),
        "current_period_end": (
            getattr(user, "subscription_current_period_end", None) if user else None
        ),
        "current_period_end_label": current_period_end_label,
        "billing_issue": (
            bool(getattr(user, "billing_issue_at", None)) if user else False
        ),
        "analyses_used": analyses_used,
        "analyses_limit": a_limit,
        "analyses_left": max((a_limit or 0) - analyses_used, 0) if a_limit else None,
        "jobs_used": jobs_used,
        "jobs_limit": j_limit,
        "jobs_left": max((j_limit or 0) - jobs_used, 0) if j_limit else None,
        "downloads_used": downloads_used,
        "downloads_limit": d_limit,
        "downloads_left": max((d_limit or 0) - downloads_used, 0) if d_limit else None,
        "can_download_tailored": plan != "free",
    }


# ── Env-based paid activation ────────────────────────────────────


def sync_paid_status(user):
    """Activate paid plan if user's email is in OFFERION_PAID_EMAILS."""
    import os

    if not user or not getattr(user, "email", None):
        return False
    paid_emails = os.environ.get("OFFERION_PAID_EMAILS", "")
    if not paid_emails:
        return False
    paid_list = [e.strip().lower() for e in paid_emails.split(",") if e.strip()]
    if user.email.lower() in paid_list:
        if (
            normalize_subscription_status(getattr(user, "subscription_status", None))
            != "active"
        ):
            apply_subscription_state(user, "active", tier_name="operator")
            return True
    return False
