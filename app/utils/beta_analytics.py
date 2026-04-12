"""Bundle V — Beta analytics and cohort helpers."""

from collections import defaultdict
from datetime import datetime


def build_activation_funnel(
    total_signups, users_with_resume, users_with_saved_jobs, users_with_packages
):
    """Return a simple activation funnel summary."""
    base = max(total_signups, 1)
    upload_pct = round(users_with_resume / base * 100, 1) if total_signups else 0
    saved_job_pct = round(users_with_saved_jobs / base * 100, 1) if total_signups else 0
    package_pct = round(users_with_packages / base * 100, 1) if total_signups else 0
    return [
        {
            "label": "Signed Up",
            "count": total_signups,
            "pct": 100 if total_signups else 0,
        },
        {"label": "Uploaded Resume", "count": users_with_resume, "pct": upload_pct},
        {"label": "Saved a Job", "count": users_with_saved_jobs, "pct": saved_job_pct},
        {"label": "Created Package", "count": users_with_packages, "pct": package_pct},
    ]


def build_signup_cohorts(users, max_rows=8):
    """Group users by ISO signup week and summarize activation progress."""
    buckets = defaultdict(
        lambda: {"signups": 0, "uploaded": 0, "saved_job": 0, "packaged": 0}
    )
    for user in users:
        created_at = getattr(user, "created_at", None)
        if not created_at:
            continue
        iso_year, iso_week, _ = created_at.isocalendar()
        key = f"{iso_year}-W{iso_week:02d}"
        bucket = buckets[key]
        bucket["signups"] += 1
        if getattr(user, "has_uploaded_resume", False):
            bucket["uploaded"] += 1
        if getattr(user, "saved_jobs", None):
            bucket["saved_job"] += 1
        if getattr(user, "application_packages", None):
            bucket["packaged"] += 1

    rows = []
    for label in sorted(buckets.keys(), reverse=True)[:max_rows]:
        bucket = buckets[label]
        signups = bucket["signups"]
        rows.append(
            {
                "label": label,
                "signups": signups,
                "uploaded_pct": (
                    round(bucket["uploaded"] / signups * 100, 1) if signups else 0
                ),
                "saved_job_pct": (
                    round(bucket["saved_job"] / signups * 100, 1) if signups else 0
                ),
                "packaged_pct": (
                    round(bucket["packaged"] / signups * 100, 1) if signups else 0
                ),
            }
        )
    return rows


def summarize_event_counts(events_by_type):
    """Normalize event counts into a founder-friendly dict."""
    return {
        "gated_hits": events_by_type.get("feature_gated", 0),
        "upgrade_attempts": events_by_type.get("upgrade_attempted", 0),
        "checkout_started": events_by_type.get("checkout_started", 0),
        "checkout_completed": events_by_type.get("checkout_success", 0),
        "alerts_created": events_by_type.get("alert_created", 0),
        "alerts_completed": events_by_type.get("alert_completed", 0),
        "email_sent": events_by_type.get("alert_email_sent", 0),
        "email_failed": events_by_type.get("alert_email_failed", 0),
        "email_skipped": events_by_type.get("alert_email_skipped", 0),
    }


def current_timestamp():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
