import logging
import os
from datetime import datetime

from flask import (
    Blueprint,
    current_app,
    redirect,
    render_template,
    request,
    session,
    url_for,
    Response,
)
from werkzeug.utils import secure_filename

from app import ALLOWED_EXTENSIONS
from app.utils.match_scorer import score_match
from app.utils.report_builder import build_report
from app.utils.resume_analyzer import analyze_resume
from app.utils.resume_parser import extract_text, get_file_extension, preview_text
from app.utils.job_compare import compare_resume_to_jd
from app.utils.resume_feedback import generate_feedback
from app.utils.rewrite_guidance import generate_rewrite_guidance
from app.utils.role_suggester import suggest_roles
from app.utils.scorecard import generate_scorecard
from app.utils.tailored_resume import generate_tailored_resume
from app.utils.storage import save_file, delete_file
from app.utils.tailored_brief import build_tailored_brief
from app.utils.action_plan import generate_action_plan
from app.utils.resume_draft_builder import build_resume_draft
from app.utils.resume_enhancer import enhance_resume
from app.utils.resume_versioning import (
    save_version,
    load_version,
    find_version,
    delete_version,
)
from app.utils.cover_letter_builder import build_cover_letter
from app.utils.cover_letter_enhancer import enhance_cover_letter
from app.utils.application_package import (
    save_package,
    load_package,
    find_package,
    delete_package,
)
from app.utils.match_explainer import explain_match
from app.utils.keyword_gap_detector import detect_keyword_gaps
from app.utils.priority_fixes import generate_priority_fixes
from app.utils.role_fit_suggestions import suggest_role_fit
from app.utils.job_tracker import (
    create_saved_job,
    update_job_status,
    find_job,
    delete_job,
    ALLOWED_STATUSES,
)
from app.utils.alerts import (
    create_alert,
    complete_alert,
    delete_alert,
    get_active_alerts,
)
from app.utils.followup_prompts import generate_followup_prompts
from app.utils.session_memory import (
    get_memory,
    update_memory,
    set_last_action,
    is_empty,
)
from app.utils.activity_timeline import record_event, get_timeline
from app.utils.provenance import build_provenance, get_source_label
from app.utils.next_best_action import get_next_action
from app.utils.identity import get_or_create_user
from app.utils.persistence import (
    persist_job,
    persist_job_status,
    remove_job as db_remove_job,
    persist_version,
    remove_version as db_remove_version,
    persist_package,
    remove_package as db_remove_package,
    persist_alert,
    persist_alert_complete,
    remove_alert as db_remove_alert,
    remove_alerts_for_job,
    persist_event,
    hydrate_session_from_db,
    persist_tier,
)
from app.utils.tier_config import (
    has_access,
    required_tier_for,
    tier_label,
    check_limit,
    TIER_CONFIG,
    TIER_ORDER,
)

logger = logging.getLogger(__name__)

main_bp = Blueprint("main", __name__)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _refresh_intelligence(report_data):
    """Generate M30-M33 intelligence data from report_data and store in session."""
    if not report_data:
        return
    match_data = report_data.get("match")
    profile = report_data.get("profile")
    tailored = report_data.get("tailored")
    rewrite = report_data.get("rewrite")
    scorecard = report_data.get("scorecard")
    enhanced = session.get("enhanced_resume")

    session["match_explanation"] = explain_match(
        match=match_data, profile=profile, tailored=tailored, rewrite=rewrite
    )
    session["keyword_gaps"] = detect_keyword_gaps(
        match=match_data, tailored=tailored, rewrite=rewrite, profile=profile
    )
    session["priority_fixes"] = generate_priority_fixes(
        match=match_data,
        profile=profile,
        tailored=tailored,
        rewrite=rewrite,
        scorecard=scorecard,
    )
    session["role_fit_suggestions"] = suggest_role_fit(
        match=match_data,
        profile=profile,
        tailored=tailored,
        rewrite=rewrite,
        enhanced_resume=enhanced,
    )


def _ensure_user():
    """Get or create user identity and hydrate session from DB."""
    user_id = get_or_create_user(session)
    if user_id:
        hydrate_session_from_db(session, user_id)
    return user_id


def _db_record_event(user_id, event):
    """Persist a timeline event to the database."""
    if user_id and event:
        persist_event(user_id, event)


def _record_activity(user_id, event_type, label, meta=None):
    """Record an activity event in session and persist it when DB is available."""
    event = record_event(session, event_type, label, meta=meta)
    _db_record_event(user_id, event)
    return event


def _same_package(existing_pkg, new_pkg):
    """Return True when two package snapshots contain the same core payload."""
    if not existing_pkg or not new_pkg:
        return False
    keys = (
        "label",
        "target_title",
        "company",
        "report_data",
        "enhanced_resume",
        "cover_letter_draft",
        "enhanced_cover_letter",
    )
    return all(existing_pkg.get(key) == new_pkg.get(key) for key in keys)


def _user_tier():
    """Return the current user's tier from session."""
    return session.get("user_tier", "free")


def _gate(feature_key):
    """Check access to *feature_key*. Returns None if allowed,
    or a redirect Response to the pricing page with an explanation flash."""
    if has_access(_user_tier(), feature_key):
        return None
    needed = required_tier_for(feature_key)
    session["gate_message"] = (
        f"You tried to access a premium feature. "
        f"Upgrade to {tier_label(needed)} or higher to continue this workflow."
    )
    return redirect(url_for("main.pricing"))


def _tier_ctx():
    """Return dict of tier-related template variables."""
    ut = _user_tier()
    return {
        "user_tier": ut,
        "tier_label": tier_label(ut),
        "has_access": lambda feat: has_access(ut, feat),
        "required_tier_for": required_tier_for,
        "check_limit": lambda key, count: check_limit(ut, key, count),
    }


def _onboarding_ctx():
    """Return onboarding-related template variables (M58)."""
    show = not session.get("has_seen_onboarding")
    step = session.get("onboarding_step", 1) if show else 0
    return {"show_onboarding": show, "onboarding_step": step}


def _increment_usage(key):
    """Increment a usage counter in session (M60)."""
    usage = session.get("usage", {})
    usage[key] = usage.get(key, 0) + 1
    session["usage"] = usage


def _upgrade_nudge():
    """Return an upgrade nudge message if warranted (M60), else None."""
    ut = _user_tier()
    if ut != "free":
        return None
    usage = session.get("usage", {})
    if usage.get("enhance_resume", 0) >= 2:
        return "You're using this like a pro \u2014 unlock full automation with Comet."
    if usage.get("generate_cl", 0) >= 2:
        return "You love cover letters \u2014 upgrade for unlimited generation."
    return None


@main_bp.before_app_request
def _bootstrap_persistence():
    """Ensure anonymous identity exists and persisted records hydrate into session."""
    session.permanent = True
    _ensure_user()


@main_bp.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    user_id = session.get("user_id")
    message = None
    error = None
    result = None
    profile = None
    match = None
    suggestions = None
    feedback = None
    jd_comparison = None
    rewrite = None
    scorecard = None
    tailored = None
    action_plan = None

    _log_event("dashboard_view")

    if request.method == "POST":
        if "resume" not in request.files:
            error = "No file selected."
        else:
            file = request.files["resume"]
            if file.filename == "":
                error = "No file selected."
            elif not allowed_file(file.filename):
                error = (
                    "Unsupported file type. Please upload a .pdf, .doc, or .docx file."
                )
            else:
                filepath, filename = save_file(file)
                if not filepath:
                    error = "Failed to save the uploaded file. Please try again."
                else:
                    logger.info("File uploaded: %s", filename)
                    _log_event("resume_uploaded", {"filename": filename})

                    try:
                        ext = get_file_extension(filename)
                        text, extract_error = extract_text(filepath)

                        if extract_error:
                            error = extract_error
                            result = {
                                "filename": filename,
                                "filetype": f".{ext}",
                                "status": "failed",
                            }
                        else:
                            message = f"Upload successful: {filename}"
                            result = {
                                "filename": filename,
                                "filetype": f".{ext}",
                                "status": "extracted",
                                "preview": preview_text(text),
                            }
                            profile = analyze_resume(text)
                            suggestions = suggest_roles(text, profile)

                            target_role = request.form.get("target_role", "").strip()
                            target_keywords = request.form.get(
                                "target_keywords", ""
                            ).strip()
                            if target_role:
                                match = score_match(
                                    text, profile, target_role, target_keywords
                                )

                            job_description = request.form.get(
                                "job_description", ""
                            ).strip()
                            if job_description:
                                jd_comparison = compare_resume_to_jd(
                                    text, profile, job_description
                                )

                            feedback = generate_feedback(
                                text, profile, match, jd_comparison
                            )

                            rewrite = generate_rewrite_guidance(
                                text, profile, match, jd_comparison
                            )

                            scorecard = generate_scorecard(
                                text, profile, match, jd_comparison
                            )

                            tailored = generate_tailored_resume(
                                text,
                                profile,
                                match,
                                jd_comparison,
                                rewrite,
                                scorecard,
                            )

                            action_plan = generate_action_plan(
                                scorecard=scorecard,
                                feedback=feedback,
                                rewrite=rewrite,
                                tailored=tailored,
                                jd_comparison=jd_comparison,
                            )

                            session["report_data"] = {
                                "result": result,
                                "profile": profile,
                                "match": match,
                                "suggestions": suggestions,
                                "feedback": feedback,
                                "jd_comparison": jd_comparison,
                                "rewrite": rewrite,
                                "scorecard": scorecard,
                                "tailored": tailored,
                                "action_plan": action_plan,
                            }

                            history = session.get("history", [])
                            history.append(
                                {
                                    "filename": result.get("filename"),
                                    "score": match.get("score") if match else None,
                                    "timestamp": datetime.now().strftime(
                                        "%Y-%m-%d %H:%M:%S"
                                    ),
                                }
                            )
                            session["history"] = history[-5:]

                            _refresh_intelligence(session["report_data"])

                            # M38/M39: session memory + timeline
                            target_role = match.get("target_role", "") if match else ""
                            update_memory(
                                session,
                                last_action="Resume analyzed",
                                active_target_title=target_role,
                            )
                            _record_activity(
                                user_id,
                                "resume_analyzed",
                                "Analyzed resume: %s" % filename,
                            )

                            logger.info("Analysis complete for: %s", filename)
                    except Exception as exc:
                        logger.error("Error processing %s: %s", filename, exc)
                        error = "An error occurred while processing the file. Please try again."
                    finally:
                        delete_file(filepath)

    history = session.get("history", [])
    resume_versions = session.get("resume_versions", [])
    application_packages = session.get("application_packages", [])
    match_explanation = session.get("match_explanation")
    keyword_gaps = session.get("keyword_gaps")
    priority_fixes = session.get("priority_fixes")
    role_fit = session.get("role_fit_suggestions")
    saved_jobs = session.get("saved_jobs", [])
    alerts = get_active_alerts(session.get("alerts", []))
    session_mem = get_memory(session)
    timeline = get_timeline(session, limit=15)
    provenance = build_provenance(session)
    next_action = get_next_action(session)
    session["next_best_action"] = next_action

    return render_template(
        "index.html",
        message=message,
        error=error,
        result=result,
        profile=profile,
        match=match,
        suggestions=suggestions,
        feedback=feedback,
        jd_comparison=jd_comparison,
        rewrite=rewrite,
        scorecard=scorecard,
        tailored=tailored,
        action_plan=action_plan,
        history=history,
        resume_versions=resume_versions,
        application_packages=application_packages,
        match_explanation=match_explanation,
        keyword_gaps=keyword_gaps,
        priority_fixes=priority_fixes,
        role_fit=role_fit,
        saved_jobs=saved_jobs,
        alerts=alerts,
        allowed_statuses=ALLOWED_STATUSES,
        session_memory=session_mem,
        session_memory_empty=is_empty(session_mem),
        activity_timeline=timeline,
        provenance=provenance,
        get_source_label=get_source_label,
        next_best_action=next_action,
        report_data_exists=bool(session.get("report_data")),
        upgrade_nudge_message=_upgrade_nudge(),
        show_quick_start=bool(session.get("report_data")) and not session.get("application_packages"),
        show_enhance_cta=bool(session.get("report_data")) and not session.get("enhanced_resume"),
        **_tier_ctx(),
        **_onboarding_ctx(),
    )


@main_bp.route("/download-report")
def download_report():
    report_data = session.get("report_data")
    if not report_data:
        return "No analysis data available. Please upload a resume first.", 400

    report_text = build_report(
        result=report_data.get("result"),
        profile=report_data.get("profile"),
        match=report_data.get("match"),
        suggestions=report_data.get("suggestions"),
        feedback=report_data.get("feedback"),
        jd_comparison=report_data.get("jd_comparison"),
        rewrite=report_data.get("rewrite"),
        scorecard=report_data.get("scorecard"),
        tailored=report_data.get("tailored"),
        action_plan=report_data.get("action_plan"),
    )

    return Response(
        report_text,
        mimetype="text/plain",
        headers={"Content-Disposition": "attachment; filename=offerion_report.txt"},
    )


@main_bp.route("/download-tailored-brief")
def download_tailored_brief():
    report_data = session.get("report_data")
    if not report_data or not report_data.get("tailored"):
        return (
            "No tailored data available. Please upload a resume with a target role or job description first.",
            400,
        )

    brief_text = build_tailored_brief(report_data["tailored"])

    return Response(
        brief_text,
        mimetype="text/plain",
        headers={
            "Content-Disposition": "attachment; filename=offerion_tailored_brief.txt"
        },
    )


@main_bp.route("/download-resume-draft")
def download_resume_draft():
    report_data = session.get("report_data")
    if not report_data:
        return "No analysis data available. Please upload a resume first.", 400

    enhanced = session.get("enhanced_resume")
    if enhanced:
        draft_text = _build_enhanced_draft(enhanced)
    else:
        draft_text = build_resume_draft(
            profile=report_data.get("profile"),
            tailored=report_data.get("tailored"),
            rewrite=report_data.get("rewrite"),
            action_plan=report_data.get("action_plan"),
            match=report_data.get("match"),
            jd_comparison=report_data.get("jd_comparison"),
        )

    if not draft_text:
        return (
            "Not enough data to generate a draft. Please upload a resume first.",
            400,
        )

    return Response(
        draft_text,
        mimetype="text/plain",
        headers={
            "Content-Disposition": "attachment; filename=offerion_resume_draft.txt"
        },
    )


def _build_enhanced_draft(enhanced):
    """Convert enhanced_resume dict to plain-text download."""
    from datetime import datetime

    lines = []
    sep = "=" * 60
    sub = "-" * 40

    lines.append(sep)
    lines.append("OFFERION ENHANCED RESUME DRAFT")
    lines.append(sep)
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    lines.append(sub)
    lines.append(enhanced.get("name") or "[Your Full Name]")
    lines.append(enhanced.get("contact") or "[email] | [phone]")
    if enhanced.get("target_title"):
        lines.append(enhanced["target_title"])
    lines.append(sub)
    lines.append("")

    lines.append("PROFESSIONAL SUMMARY")
    lines.append(sub)
    lines.append(enhanced.get("enhanced_summary", ""))
    lines.append("")

    lines.append("SKILLS")
    lines.append(sub)
    skills = enhanced.get("enhanced_skills", [])
    lines.append(", ".join(skills) if skills else "[Add skills]")
    lines.append("")

    lines.append("EXPERIENCE")
    lines.append(sub)
    for bullet in enhanced.get("enhanced_experience_bullets", []):
        lines.append(f"  \u2022 {bullet}")
    lines.append("")

    lines.append("EDUCATION")
    lines.append(sub)
    for edu in enhanced.get("enhanced_education", []):
        lines.append(f"  {edu}")
    if not enhanced.get("enhanced_education"):
        lines.append("[Degree] \u2014 [Institution]")
    lines.append("")

    if enhanced.get("ats_alignment_notes"):
        lines.append("ATS ALIGNMENT NOTES")
        lines.append(sub)
        for note in enhanced["ats_alignment_notes"]:
            lines.append(f"  i {note}")
        lines.append("")

    lines.append(sep)
    lines.append("END OF ENHANCED DRAFT")
    lines.append(sep)
    lines.append("")
    lines.append("Generated by Offerion \u2014 offerion.onrender.com")

    return "\n".join(lines)


@main_bp.route("/resume-preview")
def resume_preview():
    report_data = session.get("report_data")
    if not report_data:
        return redirect(url_for("main.dashboard"))

    profile = report_data.get("profile")
    tailored = report_data.get("tailored")
    rewrite = report_data.get("rewrite")
    match_data = report_data.get("match")
    enhanced = session.get("enhanced_resume")

    target_title = None
    if tailored:
        target_title = tailored.get("target_title")
    if not target_title and match_data:
        target_title = match_data.get("target_role")

    skills_list = []
    if tailored and tailored.get("skills_to_feature"):
        skills_list = [sf["skill"] for sf in tailored["skills_to_feature"]]
    elif profile and profile.get("skills"):
        skills_list = profile["skills"]

    education_list = []
    if profile and profile.get("education"):
        education_list = profile["education"]

    resume_versions = session.get("resume_versions", [])
    cover_letter_draft = session.get("cover_letter_draft")
    enhanced_cover_letter = session.get("enhanced_cover_letter")
    application_packages = session.get("application_packages", [])
    match_explanation = session.get("match_explanation")
    keyword_gaps = session.get("keyword_gaps")
    priority_fixes = session.get("priority_fixes")
    role_fit = session.get("role_fit_suggestions")
    saved_jobs = session.get("saved_jobs", [])
    alerts = get_active_alerts(session.get("alerts", []))

    # Generate follow-up prompts for active/selected job
    followup = None
    if saved_jobs:
        followup = generate_followup_prompts(saved_jobs[0])

    session_mem = get_memory(session)
    provenance = build_provenance(session)
    next_action = get_next_action(session)
    session["next_best_action"] = next_action

    return render_template(
        "resume_preview.html",
        profile=profile,
        tailored=tailored,
        rewrite=rewrite,
        target_title=target_title,
        skills_list=skills_list,
        education_list=education_list,
        enhanced=enhanced,
        resume_versions=resume_versions,
        cover_letter_draft=cover_letter_draft,
        enhanced_cover_letter=enhanced_cover_letter,
        application_packages=application_packages,
        match_explanation=match_explanation,
        keyword_gaps=keyword_gaps,
        priority_fixes=priority_fixes,
        role_fit=role_fit,
        saved_jobs=saved_jobs,
        alerts=alerts,
        followup=followup,
        allowed_statuses=ALLOWED_STATUSES,
        session_memory=session_mem,
        session_memory_empty=is_empty(session_mem),
        provenance=provenance,
        get_source_label=get_source_label,
        next_best_action=next_action,
        upgrade_nudge_message=_upgrade_nudge(),
        **_tier_ctx(),
    )


@main_bp.route("/enhance-resume")
def enhance_resume_route():
    blocked = _gate("enhance_resume")
    if blocked:
        return blocked
    user_id = session.get("user_id")
    report_data = session.get("report_data")
    if not report_data:
        return redirect(url_for("main.dashboard"))

    enhanced = enhance_resume(
        profile=report_data.get("profile"),
        tailored=report_data.get("tailored"),
        rewrite=report_data.get("rewrite"),
        match=report_data.get("match"),
    )

    if enhanced:
        session["enhanced_resume"] = enhanced
        set_last_action(session, "Resume enhanced")
        _record_activity(user_id, "resume_enhanced", "Enhanced resume")

    _increment_usage("enhance_resume")
    _log_event("enhance_resume_clicked")
    return redirect(url_for("main.resume_preview"))


@main_bp.route("/save-resume-version")
def save_resume_version():
    blocked = _gate("save_version")
    if blocked:
        return blocked
    user_id = session.get("user_id")
    version = save_version(session)
    if not version:
        return redirect(url_for("main.dashboard"))

    versions = session.get("resume_versions", [])
    versions.append(version)
    session["resume_versions"] = versions
    persist_version(user_id, version)
    update_memory(
        session,
        last_action="Resume version saved",
        active_resume_version_id=version["id"],
    )
    _record_activity(
        user_id,
        "version_saved",
        "Saved resume version: %s" % version.get("label", ""),
    )

    return redirect(url_for("main.resume_preview"))


@main_bp.route("/resume-version/<version_id>")
def open_resume_version(version_id):
    user_id = session.get("user_id")
    versions = session.get("resume_versions", [])
    version = find_version(versions, version_id)
    if not version:
        return redirect(url_for("main.dashboard"))

    report_data, enhanced = load_version(version)
    session["report_data"] = report_data
    session["enhanced_resume"] = enhanced
    _refresh_intelligence(report_data)
    update_memory(
        session,
        last_action="Opened resume version",
        active_resume_version_id=version_id,
    )
    _record_activity(
        user_id,
        "version_opened",
        "Opened resume version: %s" % version.get("label", ""),
    )

    return redirect(url_for("main.resume_preview"))


@main_bp.route("/resume-version/<version_id>/download")
def download_resume_version(version_id):
    versions = session.get("resume_versions", [])
    version = find_version(versions, version_id)
    if not version:
        return "Version not found.", 404

    report_data, enhanced = load_version(version)

    if enhanced:
        draft_text = _build_enhanced_draft(enhanced)
    else:
        draft_text = build_resume_draft(
            profile=report_data.get("profile"),
            tailored=report_data.get("tailored"),
            rewrite=report_data.get("rewrite"),
            action_plan=report_data.get("action_plan"),
            match=report_data.get("match"),
            jd_comparison=report_data.get("jd_comparison"),
        )

    if not draft_text:
        return "Not enough data to generate this version.", 400

    safe_label = (version.get("label") or "resume").replace(" ", "_").lower()
    filename = f"offerion_{safe_label}.txt"

    return Response(
        draft_text,
        mimetype="text/plain",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@main_bp.route("/delete-resume-version/<version_id>")
def delete_resume_version_route(version_id):
    user_id = session.get("user_id")
    versions = session.get("resume_versions", [])
    session["resume_versions"] = delete_version(versions, version_id)
    db_remove_version(user_id, version_id)
    set_last_action(session, "Resume version deleted")
    _record_activity(user_id, "version_deleted", "Deleted a resume version")
    return redirect(url_for("main.dashboard"))


# ------------------------------------------------------------------
# M26 â€” Cover Letter Draft
# ------------------------------------------------------------------


@main_bp.route("/generate-cover-letter")
def generate_cover_letter_route():
    blocked = _gate("generate_cover_letter")
    if blocked:
        return blocked
    user_id = session.get("user_id")
    report_data = session.get("report_data")
    if not report_data:
        return redirect(url_for("main.dashboard"))

    enhanced_resume = session.get("enhanced_resume")

    draft = build_cover_letter(
        profile=report_data.get("profile"),
        tailored=report_data.get("tailored"),
        rewrite=report_data.get("rewrite"),
        match=report_data.get("match"),
        enhanced_resume=enhanced_resume,
    )

    if draft:
        session["cover_letter_draft"] = draft
        set_last_action(session, "Cover letter generated")
        _record_activity(
            user_id,
            "cover_letter_generated",
            "Generated cover letter draft",
        )

    _increment_usage("generate_cl")
    _log_event("generate_cl_clicked")
    return redirect(url_for("main.resume_preview"))


# ------------------------------------------------------------------
# M27 â€” Cover Letter Enhancement
# ------------------------------------------------------------------


@main_bp.route("/enhance-cover-letter")
def enhance_cover_letter_route():
    blocked = _gate("enhance_cover_letter")
    if blocked:
        return blocked
    user_id = session.get("user_id")
    draft = session.get("cover_letter_draft")
    if not draft:
        return redirect(url_for("main.resume_preview"))

    enhanced_resume = session.get("enhanced_resume")
    enhanced_cl = enhance_cover_letter(draft, enhanced_resume)

    if enhanced_cl:
        session["enhanced_cover_letter"] = enhanced_cl
        set_last_action(session, "Cover letter enhanced")
        _record_activity(user_id, "cover_letter_enhanced", "Enhanced cover letter")

    return redirect(url_for("main.resume_preview"))


# ------------------------------------------------------------------
# M28 â€” Application Package Download
# ------------------------------------------------------------------


@main_bp.route("/download-application-package")
def download_application_package():
    blocked = _gate("download_package")
    if blocked:
        return blocked
    report_data = session.get("report_data")
    if not report_data:
        return "No analysis data available.", 400

    enhanced_resume = session.get("enhanced_resume")
    cover_letter_draft = session.get("cover_letter_draft")
    enhanced_cl = session.get("enhanced_cover_letter")

    package_text = _build_application_package_text(
        report_data, enhanced_resume, cover_letter_draft, enhanced_cl
    )

    return Response(
        package_text,
        mimetype="text/plain",
        headers={
            "Content-Disposition": "attachment; filename=offerion_application_package.txt"
        },
    )


def _build_application_package_text(
    report_data, enhanced_resume, cover_letter_draft, enhanced_cl
):
    """Assemble combined resume + cover letter plain-text package."""
    sep = "=" * 60
    sub = "-" * 40
    lines = []

    lines.append(sep)
    lines.append("OFFERION APPLICATION PACKAGE")
    lines.append(sep)
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # --- Section 1: Resume ---
    lines.append(sep)
    lines.append("SECTION 1 â€” RESUME")
    lines.append(sep)
    lines.append("")

    if enhanced_resume:
        lines.append(_build_enhanced_draft(enhanced_resume))
    else:
        draft = build_resume_draft(
            profile=report_data.get("profile"),
            tailored=report_data.get("tailored"),
            rewrite=report_data.get("rewrite"),
            action_plan=report_data.get("action_plan"),
            match=report_data.get("match"),
            jd_comparison=report_data.get("jd_comparison"),
        )
        lines.append(draft or "[Resume draft not available]")

    lines.append("")

    # --- Section 2: Cover Letter ---
    lines.append(sep)
    lines.append("SECTION 2 â€” COVER LETTER")
    lines.append(sep)
    lines.append("")

    if enhanced_cl and enhanced_cl.get("full_text"):
        lines.append(enhanced_cl["full_text"])
    elif cover_letter_draft and cover_letter_draft.get("full_text"):
        lines.append(cover_letter_draft["full_text"])
    else:
        lines.append("[Cover letter not generated yet]")

    lines.append("")
    lines.append(sep)
    lines.append("END OF APPLICATION PACKAGE")
    lines.append(sep)
    lines.append("")
    lines.append("Generated by Offerion \u2014 offerion.onrender.com")

    return "\n".join(lines)


# ------------------------------------------------------------------
# M29 â€” Application Package Versioning
# ------------------------------------------------------------------


@main_bp.route("/save-application-package")
def save_application_package_route():
    blocked = _gate("save_package")
    if blocked:
        return blocked
    user_id = session.get("user_id")
    pkg = save_package(session)
    if not pkg:
        return redirect(url_for("main.dashboard"))

    packages = session.get("application_packages", [])
    existing_pkg = next((item for item in packages if _same_package(item, pkg)), None)
    if existing_pkg:
        pkg = existing_pkg
    else:
        packages.append(pkg)
        session["application_packages"] = packages
        persist_package(user_id, pkg)
    update_memory(
        session,
        last_action="Application package saved",
        active_application_package_id=pkg["id"],
    )
    _record_activity(
        user_id,
        "package_saved",
        "Saved application package: %s" % pkg.get("label", ""),
    )

    return redirect(url_for("main.resume_preview"))


@main_bp.route("/application-package/<package_id>")
def open_application_package(package_id):
    user_id = session.get("user_id")
    packages = session.get("application_packages", [])
    pkg = find_package(packages, package_id)
    if not pkg:
        return redirect(url_for("main.dashboard"))

    report_data, enhanced_resume, cl_draft, enhanced_cl = load_package(pkg)
    session["report_data"] = report_data
    session["enhanced_resume"] = enhanced_resume
    session["cover_letter_draft"] = cl_draft
    session["enhanced_cover_letter"] = enhanced_cl
    _refresh_intelligence(report_data)
    update_memory(
        session,
        last_action="Opened application package",
        active_application_package_id=package_id,
    )
    _record_activity(
        user_id,
        "package_opened",
        "Opened application package: %s" % pkg.get("label", ""),
    )

    return redirect(url_for("main.resume_preview"))


@main_bp.route("/application-package/<package_id>/download")
def download_application_package_version(package_id):
    packages = session.get("application_packages", [])
    pkg = find_package(packages, package_id)
    if not pkg:
        return "Package not found.", 404

    report_data, enhanced_resume, cl_draft, enhanced_cl = load_package(pkg)

    package_text = _build_application_package_text(
        report_data, enhanced_resume, cl_draft, enhanced_cl
    )

    safe_label = (pkg.get("label") or "package").replace(" ", "_").lower()
    filename = f"offerion_{safe_label}_package.txt"

    return Response(
        package_text,
        mimetype="text/plain",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@main_bp.route("/delete-application-package/<package_id>")
def delete_application_package_route(package_id):
    user_id = session.get("user_id")
    packages = session.get("application_packages", [])
    session["application_packages"] = delete_package(packages, package_id)
    db_remove_package(user_id, package_id)
    set_last_action(session, "Application package deleted")
    _record_activity(user_id, "package_deleted", "Deleted an application package")
    return redirect(url_for("main.dashboard"))


# ------------------------------------------------------------------
# M34 â€” Saved Jobs Tracker
# ------------------------------------------------------------------


@main_bp.route("/save-job")
def save_job_route():
    blocked = _gate("save_job")
    if blocked:
        return blocked
    user_id = session.get("user_id")
    report_data = session.get("report_data")
    job = create_saved_job(report_data=report_data, session_data=session)
    saved_jobs = session.get("saved_jobs", [])
    saved_jobs.append(job)
    session["saved_jobs"] = saved_jobs
    persist_job(user_id, job)
    update_memory(
        session,
        last_action="Job saved",
        active_job_id=job["id"],
        active_target_title=job["title"],
        active_company=job.get("company", ""),
    )
    _record_activity(user_id, "job_saved", "Saved job: %s" % job["title"])
    _increment_usage("save_job")
    _log_event("save_job_clicked", {"title": job["title"]})
    return redirect(url_for("main.dashboard"))


@main_bp.route("/job/<job_id>")
def open_job(job_id):
    blocked = _gate("job_detail")
    if blocked:
        return blocked
    saved_jobs = session.get("saved_jobs", [])
    job = find_job(saved_jobs, job_id)
    if not job:
        return redirect(url_for("main.dashboard"))

    followup = generate_followup_prompts(job)

    return render_template(
        "job_detail.html",
        job=job,
        followup=followup,
        alerts=get_active_alerts(session.get("alerts", [])),
        allowed_statuses=ALLOWED_STATUSES,
        **_tier_ctx(),
    )


@main_bp.route("/delete-job/<job_id>")
def delete_job_route(job_id):
    user_id = session.get("user_id")
    saved_jobs = session.get("saved_jobs", [])
    session["saved_jobs"] = delete_job(saved_jobs, job_id)
    # Also clean up alerts tied to this job
    alerts = session.get("alerts", [])
    session["alerts"] = [a for a in alerts if a.get("job_id") != job_id]
    db_remove_job(user_id, job_id)
    remove_alerts_for_job(user_id, job_id)
    set_last_action(session, "Job deleted")
    _record_activity(user_id, "job_deleted", "Deleted a saved job")
    return redirect(url_for("main.dashboard"))


# ------------------------------------------------------------------
# M35 â€” Application Status Tracker
# ------------------------------------------------------------------


@main_bp.route("/job/<job_id>/status/<new_status>")
def update_job_status_route(job_id, new_status):
    blocked = _gate("job_status")
    if blocked:
        return blocked
    user_id = session.get("user_id")
    saved_jobs = session.get("saved_jobs", [])
    update_job_status(saved_jobs, job_id, new_status)
    session["saved_jobs"] = saved_jobs
    persist_job_status(user_id, job_id, new_status)
    set_last_action(session, "Job status updated to %s" % new_status)
    _record_activity(
        user_id,
        "job_status_changed",
        "Updated job status to %s" % new_status,
    )
    return redirect(url_for("main.open_job", job_id=job_id))


# ------------------------------------------------------------------
# M36 â€” Alerts Foundation
# ------------------------------------------------------------------


@main_bp.route("/create-followup-alert/<job_id>")
def create_followup_alert(job_id):
    blocked = _gate("create_alert")
    if blocked:
        return blocked
    user_id = session.get("user_id")
    saved_jobs = session.get("saved_jobs", [])
    job = find_job(saved_jobs, job_id)
    alert = create_alert(
        job_id=job_id,
        alert_type="follow_up",
        message=f"Follow up on {job['title']}" if job else "Follow up on application",
    )
    alerts = session.get("alerts", [])
    alerts.append(alert)
    session["alerts"] = alerts
    persist_alert(user_id, alert)
    set_last_action(session, "Follow-up alert created")
    _record_activity(user_id, "alert_created", "Created follow-up alert")
    return redirect(url_for("main.open_job", job_id=job_id))


@main_bp.route("/complete-alert/<alert_id>")
def complete_alert_route(alert_id):
    blocked = _gate("complete_alert")
    if blocked:
        return blocked
    user_id = session.get("user_id")
    alerts = session.get("alerts", [])
    complete_alert(alerts, alert_id)
    session["alerts"] = alerts
    persist_alert_complete(user_id, alert_id)
    set_last_action(session, "Alert completed")
    _record_activity(user_id, "alert_completed", "Completed an alert")
    return redirect(url_for("main.dashboard"))


@main_bp.route("/delete-alert/<alert_id>")
def delete_alert_route(alert_id):
    blocked = _gate("delete_alert")
    if blocked:
        return blocked
    user_id = session.get("user_id")
    alerts = session.get("alerts", [])
    session["alerts"] = delete_alert(alerts, alert_id)
    db_remove_alert(user_id, alert_id)
    set_last_action(session, "Alert deleted")
    _record_activity(user_id, "alert_deleted", "Deleted an alert")
    return redirect(url_for("main.dashboard"))


# ------------------------------------------------------------------
# M45 â€” Guided Flow (One-Click Application Prep)
# ------------------------------------------------------------------


@main_bp.route("/prepare-application")
def prepare_application():
    blocked = _gate("prepare_application")
    if blocked:
        return blocked
    user_id = session.get("user_id")
    report_data = session.get("report_data")
    if not report_data:
        return redirect(url_for("main.dashboard"))

    # Step 2: Enhance resume if not done
    if not session.get("enhanced_resume"):
        enhanced = enhance_resume(
            profile=report_data.get("profile"),
            tailored=report_data.get("tailored"),
            rewrite=report_data.get("rewrite"),
            match=report_data.get("match"),
        )
        if enhanced:
            session["enhanced_resume"] = enhanced

    # Step 3: Generate cover letter if not done
    if not session.get("cover_letter_draft"):
        draft = build_cover_letter(
            profile=report_data.get("profile"),
            tailored=report_data.get("tailored"),
            rewrite=report_data.get("rewrite"),
            match=report_data.get("match"),
            enhanced_resume=session.get("enhanced_resume"),
        )
        if draft:
            session["cover_letter_draft"] = draft

    # Step 4: Enhance cover letter if not done
    if not session.get("enhanced_cover_letter"):
        cl_draft = session.get("cover_letter_draft")
        if cl_draft:
            enhanced_cl = enhance_cover_letter(cl_draft, session.get("enhanced_resume"))
            if enhanced_cl:
                session["enhanced_cover_letter"] = enhanced_cl

    # Step 5: Save application package
    pkg = save_package(session)
    if pkg:
        packages = session.get("application_packages", [])
        existing_pkg = next(
            (item for item in packages if _same_package(item, pkg)), None
        )
        if existing_pkg:
            pkg = existing_pkg
        else:
            packages.append(pkg)
            session["application_packages"] = packages
            persist_package(user_id, pkg)
        update_memory(
            session,
            last_action="Application prepared",
            active_application_package_id=pkg["id"],
        )

    # Determine target role for event label
    target_title = ""
    match_data = report_data.get("match")
    tailored = report_data.get("tailored")
    if match_data:
        target_title = match_data.get("target_role", "")
    if not target_title and tailored:
        target_title = tailored.get("target_title", "")

    _record_activity(
        user_id,
        "application_prepared",
        "Application prepared for %s" % (target_title or "target role"),
    )

    session["next_best_action"] = get_next_action(session)

    return redirect(url_for("main.resume_preview"))


# ------------------------------------------------------------------
# M56 â€” Pricing Page + Upgrade Flow
# ------------------------------------------------------------------


@main_bp.route("/pricing")
def pricing():
    _log_event("upgrade_clicked")
    gate_message = session.pop("gate_message", None)
    return render_template(
        "pricing.html",
        tiers=TIER_CONFIG,
        tier_order=TIER_ORDER,
        gate_message=gate_message,
        **_tier_ctx(),
    )


@main_bp.route("/upgrade/<tier_name>")
def upgrade(tier_name):
    if tier_name not in TIER_ORDER:
        return redirect(url_for("main.pricing"))
    user_id = session.get("user_id")
    session["user_tier"] = tier_name
    persist_tier(user_id, tier_name)
    return redirect(url_for("main.pricing"))


# ------------------------------------------------------------------
# M58 â€” Onboarding Flow
# ------------------------------------------------------------------


@main_bp.route("/onboarding-next")
def onboarding_next():
    step = session.get("onboarding_step", 1)
    if step >= 4:
        session["has_seen_onboarding"] = True
        session.pop("onboarding_step", None)
    else:
        session["onboarding_step"] = step + 1
    return redirect(url_for("main.dashboard"))


@main_bp.route("/onboarding-dismiss")
def onboarding_dismiss():
    session["has_seen_onboarding"] = True
    session.pop("onboarding_step", None)
    return redirect(url_for("main.dashboard"))


# ------------------------------------------------------------------
# M63 — Public Landing Page
# ------------------------------------------------------------------


def _log_event(event_name, metadata=None):
    """Log an analytics event into session (M64)."""
    events = session.get("analytics_events", [])
    entry = {
        "event": event_name,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    if metadata:
        entry["meta"] = metadata
    events.append(entry)
    session["analytics_events"] = events


@main_bp.route("/")
def landing():
    # M66: capture referral param
    ref = request.args.get("ref")
    if ref:
        session["referrer"] = ref
        _log_event("referred_signup", {"referrer": ref})

    _log_event("landing_view")
    email_status = session.pop("email_capture_status", None)
    return render_template(
        "landing.html",
        referrer=session.get("referrer"),
        email_capture_status=email_status,
    )


# ------------------------------------------------------------------
# M64 — Analytics event injection into existing routes
# ------------------------------------------------------------------
# (log_event calls are added inline in dashboard, enhance, cl, save-job, pricing)


# ------------------------------------------------------------------
# M65 — Shareable Report Links (Lite)
# ------------------------------------------------------------------


@main_bp.route("/share/create")
def share_create():
    """Create a shareable snapshot of the current report."""
    import uuid

    report_data = session.get("report_data")
    if not report_data:
        return redirect(url_for("main.dashboard"))

    match_data = report_data.get("match")
    profile = report_data.get("profile")
    match_explanation = session.get("match_explanation")

    snapshot = {
        "id": uuid.uuid4().hex[:10],
        "score": match_data.get("score") if match_data else None,
        "target_role": match_data.get("target_role", "") if match_data else "",
        "top_skills": (profile.get("skills", [])[:8] if profile else []),
        "summary": (
            match_explanation.get("summary", "")
            if match_explanation
            else "Resume analyzed with Offerion."
        ),
        "strengths": (
            match_explanation.get("strengths", [])[:5] if match_explanation else []
        ),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    shared = session.get("shared_reports", [])
    shared.append(snapshot)
    session["shared_reports"] = shared

    _log_event("share_created", {"report_id": snapshot["id"]})
    return redirect(url_for("main.share_report", report_id=snapshot["id"]))


@main_bp.route("/share/report/<report_id>")
def share_report(report_id):
    """Public view of a shared report."""
    shared = session.get("shared_reports", [])
    report = next((r for r in shared if r["id"] == report_id), None)
    if not report:
        return "Report not found.", 404

    return render_template("share_report.html", report=report)


# ------------------------------------------------------------------
# M67 — Email Capture
# ------------------------------------------------------------------


@main_bp.route("/capture-email", methods=["POST"])
def capture_email():
    """Store an email address in session (no backend email service yet)."""
    import re

    email = request.form.get("email", "").strip()
    if not email or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        session["email_capture_status"] = "invalid"
        return redirect(url_for("main.landing"))

    captured = session.get("captured_emails", [])
    if email not in captured:
        captured.append(email)
        session["captured_emails"] = captured
    session["email_capture_status"] = "success"
    _log_event("email_captured")
    return redirect(url_for("main.landing"))


@main_bp.route("/<path:path>")
def fallback(path):
    return redirect(url_for("main.dashboard"))
