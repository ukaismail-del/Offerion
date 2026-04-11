"""M29 — Application Package Versioning.

Save and manage combined resume + cover letter packages per session.
"""

import copy
import uuid
from datetime import datetime


def save_package(session_data):
    """Create a snapshot of the current resume + cover letter state.

    Returns the new package dict, or None if no report data exists.
    """
    report_data = session_data.get("report_data")
    if not report_data:
        return None

    enhanced_resume = session_data.get("enhanced_resume")
    cover_letter_draft = session_data.get("cover_letter_draft")
    enhanced_cover_letter = session_data.get("enhanced_cover_letter")

    label = _build_label(report_data, enhanced_resume, session_data)
    company = _resolve_company(
        report_data, cover_letter_draft, enhanced_cover_letter, session_data
    )

    package = {
        "id": uuid.uuid4().hex[:12],
        "label": label,
        "target_title": _get_target_title(report_data, enhanced_resume),
        "company": company,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "report_data": copy.deepcopy(report_data),
        "enhanced_resume": copy.deepcopy(enhanced_resume) if enhanced_resume else None,
        "cover_letter_draft": (
            copy.deepcopy(cover_letter_draft) if cover_letter_draft else None
        ),
        "enhanced_cover_letter": (
            copy.deepcopy(enhanced_cover_letter) if enhanced_cover_letter else None
        ),
        # M100: persist selected-job intelligence alongside package
        "selected_job_intelligence": copy.deepcopy(
            session_data.get("selected_job_intelligence")
        ),
        "selected_job_gap": copy.deepcopy(session_data.get("selected_job_gap")),
    }

    return package


def load_package(package):
    """Return (report_data, enhanced_resume, cover_letter_draft, enhanced_cover_letter).

    Also stores M100 intelligence/gap data in the package dict for
    callers that need it, but maintains backward-compatible 4-tuple.
    """
    return (
        copy.deepcopy(package.get("report_data", {})),
        copy.deepcopy(package.get("enhanced_resume")),
        copy.deepcopy(package.get("cover_letter_draft")),
        copy.deepcopy(package.get("enhanced_cover_letter")),
    )


def find_package(packages, package_id):
    for p in packages:
        if p["id"] == package_id:
            return p
    return None


def delete_package(packages, package_id):
    return [p for p in packages if p["id"] != package_id]


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def _get_target_title(report_data, enhanced_resume):
    if enhanced_resume and enhanced_resume.get("target_title"):
        return enhanced_resume["target_title"]
    tailored = report_data.get("tailored")
    if tailored and tailored.get("target_title"):
        return tailored["target_title"]
    match = report_data.get("match")
    if match and match.get("target_role"):
        return match["target_role"]
    return None


def _resolve_company(
    report_data, cover_letter_draft, enhanced_cover_letter, session_data=None
):
    if enhanced_cover_letter and enhanced_cover_letter.get("company"):
        c = enhanced_cover_letter["company"]
        if c != "your organization":
            return c
    if cover_letter_draft and cover_letter_draft.get("company"):
        c = cover_letter_draft["company"]
        if c != "your organization":
            return c
    # M43: Try session memory
    if session_data:
        mem = session_data.get("session_memory", {})
        company = mem.get("active_company", "")
        if company:
            return company
    return "Unknown Company"


def _build_label(report_data, enhanced_resume, session_data):
    title = _get_target_title(report_data, enhanced_resume)
    if not title:
        # M43: Try session memory
        mem = session_data.get("session_memory", {})
        title = mem.get("active_target_title", "")
    if title:
        return title
    return "Untitled Role"
