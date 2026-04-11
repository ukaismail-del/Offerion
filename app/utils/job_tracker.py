"""M34 — Saved Jobs Tracker. Session-based job tracking utilities."""

import uuid
from datetime import datetime


def create_saved_job(report_data=None, title=None, company=None,
                     location=None, job_url=None, notes=None, source=None):
    """Create a saved job entry from explicit fields or report_data context."""
    job_title = title or ""
    job_company = company or ""

    if report_data and not job_title:
        match = report_data.get("match")
        if match:
            job_title = match.get("target_role", "")
        tailored = report_data.get("tailored")
        if not job_title and tailored:
            job_title = tailored.get("target_title", "")

    if not job_title:
        job_title = "Untitled Job"
    if not job_company:
        job_company = ""

    return {
        "id": uuid.uuid4().hex[:12],
        "title": job_title,
        "company": job_company,
        "location": location or "",
        "job_url": job_url or "",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "notes": notes or "",
        "source": source or "",
        "status": "Saved",
    }


ALLOWED_STATUSES = [
    "Saved",
    "Preparing",
    "Applied",
    "Follow-Up",
    "Interview",
    "Offer",
    "Rejected",
]


def update_job_status(saved_jobs, job_id, new_status):
    """Update the status of a saved job. Returns True if updated."""
    if new_status not in ALLOWED_STATUSES:
        return False
    for job in saved_jobs:
        if job["id"] == job_id:
            job["status"] = new_status
            return True
    return False


def find_job(saved_jobs, job_id):
    """Find a saved job by ID."""
    for job in saved_jobs:
        if job["id"] == job_id:
            return job
    return None


def delete_job(saved_jobs, job_id):
    """Return list with the specified job removed."""
    return [j for j in saved_jobs if j["id"] != job_id]
