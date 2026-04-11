"""M36 — Alerts Foundation. Session-based alert/reminder utilities."""

import uuid
from datetime import datetime, timedelta


def create_alert(job_id, alert_type="follow_up", message=None, due_days=7):
    """Create an alert record tied to a job.

    alert_type: 'follow_up', 'deadline', or 'check_in'
    due_days: number of days from now for the due date
    """
    valid_types = ("follow_up", "deadline", "check_in")
    if alert_type not in valid_types:
        alert_type = "follow_up"

    if not message:
        messages = {
            "follow_up": "Follow up on your application",
            "deadline": "Application deadline approaching",
            "check_in": "Check in on application status",
        }
        message = messages.get(alert_type, "Reminder")

    due_at = (datetime.now() + timedelta(days=due_days)).strftime("%Y-%m-%d")

    return {
        "id": uuid.uuid4().hex[:12],
        "job_id": job_id or "",
        "type": alert_type,
        "message": message,
        "due_at": due_at,
        "is_complete": False,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def complete_alert(alerts, alert_id):
    """Mark an alert as complete. Returns True if found."""
    for alert in alerts:
        if alert["id"] == alert_id:
            alert["is_complete"] = True
            return True
    return False


def delete_alert(alerts, alert_id):
    """Return list with the specified alert removed."""
    return [a for a in alerts if a["id"] != alert_id]


def find_alert(alerts, alert_id):
    """Find an alert by ID."""
    for alert in alerts:
        if alert["id"] == alert_id:
            return alert
    return None


def get_active_alerts(alerts):
    """Return only incomplete alerts, sorted by due date."""
    active = [a for a in alerts if not a.get("is_complete")]
    active.sort(key=lambda a: a.get("due_at", ""))
    return active
