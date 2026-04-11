"""M39 — Activity Timeline / Audit Trail.

Lightweight session-based history of user actions in Offerion.
"""

import uuid
from datetime import datetime

MAX_EVENTS = 30


def record_event(session, event_type, label, meta=None):
    """Add an event to the activity timeline stored in session."""
    timeline = session.get("activity_timeline", [])
    event = {
        "id": uuid.uuid4().hex[:10],
        "event_type": event_type,
        "label": label,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "meta": meta or {},
    }
    timeline.insert(0, event)
    session["activity_timeline"] = timeline[:MAX_EVENTS]
    return event


def get_timeline(session, limit=None):
    """Return the activity timeline (latest first)."""
    timeline = session.get("activity_timeline", [])
    if limit:
        return timeline[:limit]
    return timeline


def clear_timeline(session):
    """Reset the activity timeline."""
    session["activity_timeline"] = []
