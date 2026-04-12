"""Bundle U — Beta Activation Checklist.

Lightweight in-app checklist that tracks user activation milestones.
Progress is derived from actual DB/session state — no separate tracking table.
"""

from app.models import ActivityEvent

CHECKLIST_ITEMS = [
    {
        "key": "upload_resume",
        "label": "Upload your resume",
        "description": "Upload a PDF or DOCX to start your analysis",
        "route": "/dashboard",
        "icon": "📄",
    },
    {
        "key": "review_report",
        "label": "Review your match report",
        "description": "See your score, gaps, and tailored guidance",
        "route": "/resume-preview",
        "icon": "📊",
    },
    {
        "key": "save_job",
        "label": "Save a job",
        "description": "Save a recommended job to track your applications",
        "route": "/dashboard#section-jobs",
        "icon": "💼",
    },
    {
        "key": "generate_cover_letter",
        "label": "Generate a cover letter",
        "description": "Create a targeted cover letter from your resume data",
        "route": "/generate-cover-letter",
        "icon": "✉️",
    },
    {
        "key": "prepare_package",
        "label": "Prepare an application package",
        "description": "Bundle your resume and cover letter for a specific job",
        "route": "/prepare-application",
        "icon": "📦",
    },
    {
        "key": "explore_upgrade",
        "label": "Explore upgrade options",
        "description": "See what premium features can unlock for you",
        "route": "/pricing",
        "icon": "⭐",
    },
]


def get_checklist_state(user=None, session=None):
    """Build the activation checklist with completion state.

    Uses DB user record and session data to determine which items
    are complete.  Returns a dict with items list, count, total, and
    completion percentage.
    """
    completed = set()
    show_upgrade_item = False

    # Check from DB user flags
    if user:
        if getattr(user, "has_uploaded_resume", False):
            completed.add("upload_resume")
        if getattr(user, "has_generated_matches", False):
            completed.add("review_report")

        try:
            if getattr(user, "saved_jobs", None):
                completed.add("save_job")
            if getattr(user, "application_packages", None):
                completed.add("prepare_package")
        except Exception:
            # Relationship loading should never block checklist rendering.
            pass

        user_tier = getattr(user, "tier", "free") or "free"
        if user_tier not in ("free", "trial"):
            completed.add("explore_upgrade")
            show_upgrade_item = True

        user_id = getattr(user, "id", None)
        if user_id:
            try:
                cover_letter_events = ActivityEvent.query.filter(
                    ActivityEvent.user_id == user_id,
                    ActivityEvent.event_type.in_(
                        ["cover_letter_generated", "cover_letter_enhanced"]
                    ),
                ).count()
                if cover_letter_events:
                    completed.add("generate_cover_letter")

                gate_events = ActivityEvent.query.filter(
                    ActivityEvent.user_id == user_id,
                    ActivityEvent.event_type.in_(["feature_gated", "usage_limit_hit"]),
                ).count()
                if gate_events:
                    completed.add("explore_upgrade")
                    show_upgrade_item = True
            except Exception:
                # Keep checklist resilient if event queries fail.
                pass

    # Check from session state
    if session:
        if session.get("report_data"):
            completed.add("upload_resume")
            completed.add("review_report")

        saved_jobs = session.get("saved_jobs", [])
        if saved_jobs:
            completed.add("save_job")

        if session.get("cover_letter_draft") or session.get("enhanced_cover_letter"):
            completed.add("generate_cover_letter")

        packages = session.get("application_packages", [])
        if packages:
            completed.add("prepare_package")

        # Mark explore_upgrade only after a gated attempt (or paid tier).
        tier = session.get("user_tier", "free")
        if tier not in ("free", "trial"):
            completed.add("explore_upgrade")
            show_upgrade_item = True
        if session.get("_has_hit_gate"):
            completed.add("explore_upgrade")
            show_upgrade_item = True

    items = []
    for item in CHECKLIST_ITEMS:
        if item["key"] == "explore_upgrade" and not show_upgrade_item:
            continue
        items.append(
            {
                **item,
                "done": item["key"] in completed,
            }
        )

    visible_keys = {item["key"] for item in items}
    done_count = len([key for key in completed if key in visible_keys])
    total = len(items)

    return {
        "items": items,
        "done_count": done_count,
        "total": total,
        "pct": round(done_count / total * 100) if total else 0,
        "all_done": done_count >= total,
    }
