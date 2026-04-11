"""M37 — Follow-Up / Reminder Prompts.

Generate status-based recommended actions, message templates,
and next steps for saved jobs.
"""


def generate_followup_prompts(job):
    """Generate follow-up prompts based on a saved job's current status.

    Returns dict with job_id, status, recommended_actions,
    message_templates, and next_step.
    """
    if not job:
        return {
            "job_id": "",
            "status": "",
            "recommended_actions": [],
            "message_templates": [],
            "next_step": "",
        }

    status = job.get("status", "Saved")
    title = job.get("title", "the position")
    company = job.get("company", "the company")

    actions = _get_actions(status, title, company)
    templates = _get_templates(status, title, company)
    next_step = _get_next_step(status)

    return {
        "job_id": job.get("id", ""),
        "status": status,
        "recommended_actions": actions,
        "message_templates": templates,
        "next_step": next_step,
    }


def _get_actions(status, title, company):
    """Return recommended actions for the given status."""
    actions_map = {
        "Saved": [
            f"Tailor your resume for {title}",
            "Draft a targeted cover letter",
            "Research the company and role requirements",
            "Identify keywords from the job description",
        ],
        "Preparing": [
            "Review and finalize your tailored resume",
            "Proofread your cover letter",
            "Prepare your application package for submission",
            "Double-check application requirements and deadlines",
        ],
        "Applied": [
            "Set a follow-up reminder for 5–7 business days",
            "Connect with the hiring manager on LinkedIn",
            "Continue applying to similar roles",
            "Prepare talking points for a potential phone screen",
        ],
        "Follow-Up": [
            "Send a polite follow-up email",
            "Check the application portal for status updates",
            "Consider reaching out via LinkedIn",
            "Keep applying to other opportunities",
        ],
        "Interview": [
            "Research the company's recent news and culture",
            "Prepare answers to common interview questions",
            "Prepare questions to ask the interviewer",
            "Send a thank-you email within 24 hours after the interview",
        ],
        "Offer": [
            "Review the offer details carefully",
            "Compare compensation and benefits to your expectations",
            "Negotiate if appropriate",
            "Request the offer in writing if not already provided",
        ],
        "Rejected": [
            "Send a thank-you note for the opportunity",
            "Request feedback if possible",
            "Archive this application and move on",
            "Look for similar roles that match your profile",
        ],
    }
    return actions_map.get(status, ["Review your application status"])


def _get_templates(status, title, company):
    """Return short, professional message templates for the given status."""
    company_ref = company if company else "your company"

    templates_map = {
        "Saved": [],
        "Preparing": [],
        "Applied": [
            f"I recently submitted my application for {title} at {company_ref} "
            f"and wanted to follow up on the status of my application.",
            f"Thank you for considering my application for {title}. "
            f"I remain very interested in the opportunity and would welcome "
            f"the chance to discuss how I can contribute.",
        ],
        "Follow-Up": [
            f"I wanted to follow up on my application for {title} at "
            f"{company_ref}. I am still very interested in the role and "
            f"would appreciate any update on the hiring timeline.",
            f"Following up on my application for {title}. Please let me "
            f"know if any additional information would be helpful.",
        ],
        "Interview": [
            f"Thank you for taking the time to interview me for {title} "
            f"at {company_ref}. I enjoyed learning more about the team "
            f"and am excited about the opportunity.",
            f"I appreciate the opportunity to interview for {title}. "
            f"I look forward to hearing about next steps.",
        ],
        "Offer": [
            f"Thank you for extending the offer for {title} at "
            f"{company_ref}. I am reviewing the details and will "
            f"respond by the requested date.",
        ],
        "Rejected": [
            f"Thank you for considering me for {title} at {company_ref}. "
            f"I appreciate the opportunity and would welcome the chance "
            f"to be considered for future openings.",
        ],
    }
    return templates_map.get(status, [])


def _get_next_step(status):
    """Return a concise next-step suggestion."""
    steps = {
        "Saved": "Tailor your resume and cover letter for this role, then submit your application.",
        "Preparing": "Finalize your application materials and submit before the deadline.",
        "Applied": "Wait 5–7 business days, then follow up if you haven't heard back.",
        "Follow-Up": "Send a brief follow-up email and continue applying elsewhere.",
        "Interview": "Prepare thoroughly, then send a thank-you note within 24 hours.",
        "Offer": "Review the offer, negotiate if needed, and respond by the deadline.",
        "Rejected": "Archive this application and redirect your effort to similar opportunities.",
    }
    return steps.get(status, "Review your current application status and plan next actions.")
