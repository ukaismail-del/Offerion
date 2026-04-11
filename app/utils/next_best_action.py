"""M42 — Next Best Action Engine.

Suggests the most logical next step based on current session state.
"""


def get_next_action(session):
    """Determine the next best action based on session state.

    Returns a dict with label, route, reason, and priority.
    """
    report_data = session.get("report_data")
    enhanced_resume = session.get("enhanced_resume")
    cover_letter_draft = session.get("cover_letter_draft")
    enhanced_cover_letter = session.get("enhanced_cover_letter")
    application_packages = session.get("application_packages", [])
    saved_jobs = session.get("saved_jobs", [])

    if not report_data:
        return {
            "label": "Analyze Resume",
            "route": "/",
            "reason": "Upload and analyze your resume to get started",
            "priority": "high",
        }

    if not enhanced_resume:
        return {
            "label": "Enhance Resume",
            "route": "/enhance-resume",
            "reason": "Improve clarity and ATS alignment before applying",
            "priority": "high",
        }

    if not cover_letter_draft:
        return {
            "label": "Generate Cover Letter",
            "route": "/generate-cover-letter",
            "reason": "Create a tailored cover letter for your target role",
            "priority": "high",
        }

    if not enhanced_cover_letter:
        return {
            "label": "Enhance Cover Letter",
            "route": "/enhance-cover-letter",
            "reason": "Polish your cover letter for professional tone and alignment",
            "priority": "medium",
        }

    if not application_packages:
        return {
            "label": "Save Application Package",
            "route": "/save-application-package",
            "reason": "Save your resume and cover letter as a complete application package",
            "priority": "medium",
        }

    if not saved_jobs:
        return {
            "label": "Save Job",
            "route": "/save-job",
            "reason": "Track your target job for status updates and follow-ups",
            "priority": "medium",
        }

    latest_job = saved_jobs[-1]
    if latest_job.get("status") == "Saved":
        return {
            "label": "Update Status to Applied",
            "route": "/job/%s/status/Applied" % latest_job["id"],
            "reason": "Mark your latest job as applied to track progress",
            "priority": "low",
        }

    return {
        "label": "Review & Apply",
        "route": "/resume-preview",
        "reason": "Review your application materials and apply",
        "priority": "low",
    }
