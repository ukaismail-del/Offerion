import copy
import uuid
from datetime import datetime


def save_version(session_data):
    """Create a new resume version snapshot from current session state.

    Returns the new version dict, or None if no report data exists.
    """
    report_data = session_data.get("report_data")
    if not report_data:
        return None

    enhanced = session_data.get("enhanced_resume")

    # Determine label
    label = _build_label(report_data, enhanced, session_data)

    version = {
        "id": uuid.uuid4().hex[:12],
        "label": label,
        "target_title": _get_target_title(report_data, enhanced),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "report_data": copy.deepcopy(report_data),
        "enhanced_resume": copy.deepcopy(enhanced) if enhanced else None,
    }

    return version


def load_version(version):
    """Return (report_data, enhanced_resume) from a saved version."""
    return (
        copy.deepcopy(version.get("report_data", {})),
        copy.deepcopy(version.get("enhanced_resume")),
    )


def find_version(versions, version_id):
    """Find a version by id in the versions list."""
    for v in versions:
        if v["id"] == version_id:
            return v
    return None


def delete_version(versions, version_id):
    """Remove a version by id. Returns the updated list."""
    return [v for v in versions if v["id"] != version_id]


def _get_target_title(report_data, enhanced):
    if enhanced and enhanced.get("target_title"):
        return enhanced["target_title"]
    tailored = report_data.get("tailored")
    if tailored and tailored.get("target_title"):
        return tailored["target_title"]
    match = report_data.get("match")
    if match and match.get("target_role"):
        return match["target_role"]
    return None


def _build_label(report_data, enhanced, session_data):
    title = _get_target_title(report_data, enhanced)
    if not title:
        # M43: Try session memory
        mem = session_data.get("session_memory", {})
        title = mem.get("active_target_title", "")
    if title:
        return title
    return "Untitled Role"
