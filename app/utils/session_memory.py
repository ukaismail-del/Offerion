"""M38 — Job Search Session Memory.

Lightweight structured memory of the user's current Offerion workflow state.
"""

from datetime import datetime


def get_memory(session):
    """Return current session memory, creating default if absent."""
    return session.get("session_memory", _default_memory())


def _default_memory():
    return {
        "active_job_id": "",
        "active_resume_version_id": "",
        "active_application_package_id": "",
        "last_action": "",
        "last_updated_at": "",
        "active_target_title": "",
        "active_company": "",
    }


def update_memory(session, **kwargs):
    """Update session memory fields. Only provided kwargs are changed."""
    mem = session.get("session_memory", _default_memory())
    for key, value in kwargs.items():
        if key in mem:
            mem[key] = value
    mem["last_updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    session["session_memory"] = mem
    return mem


def set_last_action(session, action):
    """Convenience: update only the last_action field."""
    return update_memory(session, last_action=action)


def clear_memory(session):
    """Reset session memory to defaults."""
    session["session_memory"] = _default_memory()


def is_empty(memory):
    """Return True if memory has no meaningful content."""
    if not memory:
        return True
    return not any(
        memory.get(k)
        for k in (
            "active_job_id",
            "active_resume_version_id",
            "active_application_package_id",
            "last_action",
        )
    )
