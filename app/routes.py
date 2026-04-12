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
    start_trial,
    trial_days_remaining,
    check_trial_expiry,
)
from app.utils.billing import (
    get_user_plan_state,
    can_run_resume_analysis,
    can_view_jobs,
    can_download_tailored_resume,
    can_download_report,
    record_resume_analysis_usage,
    record_job_view_usage,
    record_resume_download_usage,
    get_upgrade_reason,
    get_usage_summary,
    sync_paid_status,
    reset_monthly_usage_if_needed,
)
from app.utils.job_data import find_job_by_id
from app.utils.job_feed import get_unified_jobs
from app.utils.job_matcher import match_jobs
from app.utils.job_intelligence import extract_job_intelligence
from app.utils.job_gap_analyzer import analyze_job_gap
from app.db import db as app_db
from app.models import UserIdentity, ActivityEvent

logger = logging.getLogger(__name__)

main_bp = Blueprint("main", __name__)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ------------------------------------------------------------------
# M99 — Selected-job session state helper
# ------------------------------------------------------------------


def _selected_job_state():
    """Return a consistent (intel, gap, context) triplet from session.

    Each value is either a well-formed dict or ``None``.  Templates can
    rely on the keys existing when the value is not ``None``.
    """
    report_data = session.get("report_data")
    context = (report_data or {}).get("job_context") if report_data else None
    intel = session.get("selected_job_intelligence")
    gap = session.get("selected_job_gap")

    # Normalise: if context exists but intel/gap are missing, regenerate
    if context and (not intel or not gap):
        try:
            job_payload = {
                "title": context.get("title", ""),
                "description": context.get("description", ""),
                "skills": context.get("skills", []),
                "company": context.get("company", ""),
            }
            if not intel:
                intel = extract_job_intelligence(job_payload)
                session["selected_job_intelligence"] = intel
            if not gap and report_data:
                gap = analyze_job_gap(report_data, job_payload)
                session["selected_job_gap"] = gap
        except Exception:
            logger.debug("_selected_job_state: regeneration failed", exc_info=True)

    return intel, gap, context


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


def _log_db_activity(user_id, event_type, event_label=None, meta=None):
    """Write a structured ActivityEvent row to the database."""
    if not user_id:
        return
    try:
        import json as _json

        evt = ActivityEvent(
            user_id=user_id,
            event_type=event_type,
            event_label=event_label or "",
            label=event_label or "",
            meta_json=_json.dumps(meta) if meta else "{}",
        )
        app_db.session.add(evt)
        app_db.session.commit()
    except Exception:
        app_db.session.rollback()


def _check_onboarding_complete(user):
    """Mark onboarding complete if both flags are set and not already marked."""
    if (
        user
        and getattr(user, "has_uploaded_resume", False)
        and getattr(user, "has_generated_matches", False)
        and not user.onboarding_completed_at
    ):
        user.onboarding_completed_at = datetime.utcnow()
        app_db.session.commit()
        _log_db_activity(user.id, "onboarding_completed", "Onboarding completed")


def _sync_admin_flag(user):
    """Promote user to admin if their email is in OFFERION_ADMIN_EMAILS env var."""
    admin_emails = os.environ.get("OFFERION_ADMIN_EMAILS", "")
    if not admin_emails or not user or not user.email:
        return
    admin_list = [e.strip().lower() for e in admin_emails.split(",") if e.strip()]
    if user.email.lower() in admin_list:
        user.is_admin = True
        app_db.session.commit()


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
    # Feature-specific gate messages for conversion clarity (M118)
    gate_messages = {
        "enhance_resume": (
            "AI resume enhancement is available on Comet and above. "
            "Upgrade to get a polished, ATS-optimized version of your resume."
        ),
        "generate_cover_letter": (
            "Cover letter generation requires Comet or higher. "
            "Upgrade to create targeted cover letters from your resume data."
        ),
        "enhance_cover_letter": (
            "Cover letter enhancement is available on Operator and above. "
            "Upgrade to refine your cover letter with job-specific targeting."
        ),
        "save_package": (
            "Application packages are an Operator feature. "
            "Upgrade to save and manage complete application bundles."
        ),
        "prepare_application": (
            "One-click application prep is an Operator feature. "
            "Upgrade to generate a full application package in one step."
        ),
        "save_job": (
            "Job tracking is available on Operator and above. "
            "Upgrade to save, manage, and track your job applications."
        ),
        "create_alert": (
            "Follow-up alerts are a Professional feature. "
            "Upgrade to set reminders and never miss an application follow-up."
        ),
    }
    session["gate_message"] = gate_messages.get(
        feature_key,
        f"This feature requires {tier_label(needed)} or higher. "
        f"Upgrade to unlock it and continue your workflow.",
    )
    session["gate_return_to"] = request.path
    return redirect(url_for("main.pricing"))


def _tier_ctx():
    """Return dict of tier-related template variables."""
    ut = _user_tier()
    trial_days = session.get("trial_days_left")
    return {
        "user_tier": ut,
        "tier_label": tier_label(ut),
        "has_access": lambda feat: has_access(ut, feat),
        "required_tier_for": required_tier_for,
        "check_limit": lambda key, count: check_limit(ut, key, count),
        "trial_days_left": trial_days,
        "is_trial": ut == "trial",
    }


def _billing_ctx(user_id):
    """Return billing/usage summary for template rendering."""
    if not user_id:
        return get_usage_summary(None)
    try:
        user = UserIdentity.query.get(user_id)
        return get_usage_summary(user)
    except Exception:
        return get_usage_summary(None)


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
    trial_days = session.get("trial_days_left")
    if ut == "trial" and trial_days is not None and trial_days <= 2:
        return (
            "Your trial ends soon — choose a plan to keep job-targeted prep, "
            "tracking, and follow-up tools active."
        )
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
    """Ensure authenticated user's session is hydrated from DB."""
    session.permanent = True

    # Public routes that don't require authentication
    path = request.path
    is_public = (
        path in ("/", "/login", "/signup", "/pricing", "/capture-email")
        or path.startswith("/share/")
        or path.startswith("/static/")
    )

    if not is_public and not session.get("is_authenticated"):
        # In testing mode, allow session-seeded users through
        if not (current_app.config.get("TESTING") and session.get("user_id")):
            return redirect(url_for("main.login_page"))

    # Hydrate session for authenticated users (or test users with user_id)
    if session.get("user_id"):
        _ensure_user()
        # Bundle W — plan state sync on each request
        try:
            _bw_user = UserIdentity.query.get(session["user_id"])
            if _bw_user:
                check_trial_expiry(_bw_user)
                sync_paid_status(_bw_user)
                reset_monthly_usage_if_needed(_bw_user)
                app_db.session.commit()
                session["user_tier"] = _bw_user.tier or "free"
                days_left = trial_days_remaining(_bw_user)
                session["trial_days_left"] = days_left
        except Exception:
            app_db.session.rollback()


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
        # Bundle W — enforce resume analysis limit
        _bw_analysis_user = UserIdentity.query.get(user_id) if user_id else None
        if _bw_analysis_user and not can_run_resume_analysis(_bw_analysis_user):
            _reason = get_upgrade_reason(_bw_analysis_user, "resume_analysis")
            error = (
                _reason or "You\u2019ve reached your analysis limit. Upgrade for more."
            )
            _log_db_activity(
                user_id,
                "usage_limit_hit",
                "Resume analysis limit",
                {"action": "resume_analysis"},
            )
        elif "resume" not in request.files:
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

                            # Bundle V: onboarding tracking
                            if user_id:
                                try:
                                    _user = UserIdentity.query.get(user_id)
                                    if _user:
                                        if not _user.has_uploaded_resume:
                                            _user.has_uploaded_resume = True
                                            _log_db_activity(
                                                user_id,
                                                "resume_uploaded",
                                                "Resume uploaded: %s" % filename,
                                            )
                                        if profile and not _user.has_generated_matches:
                                            _user.has_generated_matches = True
                                            _log_db_activity(
                                                user_id,
                                                "match_generated",
                                                "Match/report generated",
                                            )
                                        app_db.session.commit()
                                        _check_onboarding_complete(_user)
                                except Exception:
                                    app_db.session.rollback()

                            # Bundle W: record resume analysis usage
                            if user_id:
                                try:
                                    _bw_u = UserIdentity.query.get(user_id)
                                    if _bw_u:
                                        record_resume_analysis_usage(_bw_u)
                                        app_db.session.commit()
                                except Exception:
                                    app_db.session.rollback()

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

    report_data = session.get("report_data")

    # ── M119 — Usage visibility signals ──────────────────────────
    usage_signals = []
    if report_data:
        usage_signals.append("Resume analyzed")
    selected_ctx = _selected_job_state()[2]
    if selected_ctx:
        usage_signals.append(
            "Targeting active for %s" % selected_ctx.get("title", "selected job")
        )
    if session.get("enhanced_resume"):
        usage_signals.append("Resume enhanced")
    if session.get("cover_letter_draft") or session.get("enhanced_cover_letter"):
        usage_signals.append("Application draft ready")

    # ── Job filters (M77) ────────────────────────────────────────
    job_query = request.args.get("job_query", "").strip()
    job_location = request.args.get("job_location", "").strip()
    job_remote = request.args.get("job_remote", "").strip()
    job_source = request.args.get("job_source", "").strip()
    remote_flag = (
        True if job_remote == "true" else (False if job_remote == "false" else None)
    )

    jobs_used_fallback = False
    if report_data:
        # Extract resume skills to drive API query (different resumes → different jobs)
        _resume_skills_for_query = []
        _profile = report_data.get("profile")
        _match_data = report_data.get("match")
        _target_role = ""
        _resume_text = ""
        if _profile and _profile.get("skills"):
            _resume_skills_for_query = [
                s.lower().strip()
                for s in _profile["skills"]
                if s and s.strip().lower() != "not detected"
            ]
        if _match_data and _match_data.get("target_role"):
            _target_role = _match_data["target_role"]
        if session.get("resume_text"):
            _resume_text = session["resume_text"]

        filtered_jobs = get_unified_jobs(
            query=job_query or None,
            location=job_location or None,
            remote=remote_flag,
            source=job_source or None,
            resume_skills=_resume_skills_for_query if not job_query else None,
            target_role=_target_role if not job_query else None,
            resume_text=_resume_text if not job_query else None,
        )
        jobs_used_fallback = getattr(filtered_jobs, "used_fallback", False)
        recommended_jobs = match_jobs(report_data, jobs=filtered_jobs)

        # Bundle W — job view enforcement
        _bw_jv_user = UserIdentity.query.get(user_id) if user_id else None
        jobs_capped = False
        if _bw_jv_user:
            if not can_view_jobs(_bw_jv_user):
                jobs_capped = True
                recommended_jobs = []
                _log_db_activity(
                    user_id,
                    "usage_limit_hit",
                    "Job view limit",
                    {"action": "job_views"},
                )
            elif recommended_jobs:
                record_job_view_usage(_bw_jv_user, count=len(recommended_jobs))
                try:
                    app_db.session.commit()
                except Exception:
                    app_db.session.rollback()
    else:
        recommended_jobs = []
        jobs_capped = False

    # Bundle V: onboarding progress for dashboard
    onboarding_progress = {
        "created": True,
        "resume": False,
        "matches": False,
        "complete": False,
        "count": 1,
    }
    if user_id:
        try:
            _ob_user = UserIdentity.query.get(user_id)
            if _ob_user:
                onboarding_progress["resume"] = bool(
                    getattr(_ob_user, "has_uploaded_resume", False)
                )
                onboarding_progress["matches"] = bool(
                    getattr(_ob_user, "has_generated_matches", False)
                )
                onboarding_progress["complete"] = bool(_ob_user.onboarding_completed_at)
                onboarding_progress["count"] = (
                    1
                    + int(onboarding_progress["resume"])
                    + int(onboarding_progress["matches"])
                )
        except Exception:
            pass

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
        recommended_jobs=recommended_jobs,
        jobs_used_fallback=jobs_used_fallback,
        job_query=job_query,
        job_location=job_location,
        job_remote=job_remote,
        job_source=job_source,
        selected_job_intel=_selected_job_state()[0],
        selected_job_gap=_selected_job_state()[1],
        selected_job_context=_selected_job_state()[2],
        show_quick_start=bool(session.get("report_data"))
        and not session.get("application_packages"),
        show_enhance_cta=bool(session.get("report_data"))
        and not session.get("enhanced_resume"),
        dashboard_notice_message=session.pop("dashboard_notice_message", None),
        package_recovery_message=session.pop("package_recovery_message", None),
        usage_signals=usage_signals,
        onboarding_progress=onboarding_progress,
        jobs_capped=jobs_capped,
        billing=_billing_ctx(user_id),
        **_tier_ctx(),
        **_onboarding_ctx(),
    )


@main_bp.route("/download-report")
def download_report():
    # Bundle W — enforce report download limit
    user_id = session.get("user_id")
    _bw_dl_user = UserIdentity.query.get(user_id) if user_id else None
    if _bw_dl_user and not can_download_report(_bw_dl_user):
        _reason = get_upgrade_reason(_bw_dl_user, "report")
        session["gate_message"] = (
            _reason or "Report download limit reached. Upgrade for more."
        )
        _log_db_activity(
            user_id, "usage_limit_hit", "Report download limit", {"action": "report"}
        )
        return redirect(url_for("main.pricing"))

    report_data = session.get("report_data")
    if not report_data:
        return "No analysis data available. Please upload a resume first.", 400

    # Record download usage
    if _bw_dl_user:
        record_resume_download_usage(_bw_dl_user)
        try:
            app_db.session.commit()
        except Exception:
            app_db.session.rollback()

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
    # Bundle W — free users cannot download tailored resume
    user_id = session.get("user_id")
    _bw_tb_user = UserIdentity.query.get(user_id) if user_id else None
    if _bw_tb_user and not can_download_tailored_resume(_bw_tb_user):
        session["gate_message"] = (
            "Tailored resume downloads are available on Trial and Paid plans. Upgrade to unlock."
        )
        _log_db_activity(
            user_id,
            "usage_limit_hit",
            "Tailored resume blocked",
            {"action": "tailored_resume"},
        )
        return redirect(url_for("main.pricing"))

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
        # M113: Render a safe empty state instead of hard redirect
        return render_template(
            "resume_preview.html",
            profile=None,
            tailored=None,
            rewrite=None,
            target_title=None,
            skills_list=[],
            education_list=[],
            enhanced=None,
            resume_versions=session.get("resume_versions", []),
            cover_letter_draft=None,
            enhanced_cover_letter=None,
            application_packages=session.get("application_packages", []),
            match_explanation=None,
            keyword_gaps=None,
            priority_fixes=None,
            role_fit=None,
            saved_jobs=session.get("saved_jobs", []),
            alerts=get_active_alerts(session.get("alerts", [])),
            followup=None,
            allowed_statuses=ALLOWED_STATUSES,
            session_memory=get_memory(session),
            session_memory_empty=is_empty(get_memory(session)),
            provenance=build_provenance(session),
            get_source_label=get_source_label,
            next_best_action=get_next_action(session),
            upgrade_nudge_message=None,
            selected_job_intel=None,
            selected_job_gap=None,
            selected_job_context=None,
            preview_notice_message=session.pop("resume_preview_message", None),
            no_report=True,
            usage_signals=[],
            **_tier_ctx(),
        )

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

    # ── M119 — Usage visibility signals for preview ──────────────
    usage_signals = ["Resume analyzed"]
    sel_ctx = _selected_job_state()[2]
    if sel_ctx:
        usage_signals.append(
            "Targeting active for %s" % sel_ctx.get("title", "selected job")
        )
    if enhanced:
        usage_signals.append("Resume enhanced")
    if cover_letter_draft or enhanced_cover_letter:
        usage_signals.append("Application draft ready")
    if session.pop("package_recovery_message", None) is not None:
        usage_signals.append("Recovered from saved package")

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
        selected_job_intel=_selected_job_state()[0],
        selected_job_gap=_selected_job_state()[1],
        selected_job_context=_selected_job_state()[2],
        preview_notice_message=session.pop("resume_preview_message", None),
        no_report=False,
        usage_signals=usage_signals,
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
        session["dashboard_notice_message"] = (
            "Start with a resume analysis before enhancing your draft."
        )
        return redirect(url_for("main.dashboard"))

    enhanced = enhance_resume(
        profile=report_data.get("profile"),
        tailored=report_data.get("tailored"),
        rewrite=report_data.get("rewrite"),
        match=report_data.get("match"),
        job_context=report_data.get("job_context"),
    )

    if enhanced:
        session["enhanced_resume"] = enhanced
        set_last_action(session, "Resume enhanced")
        _record_activity(user_id, "resume_enhanced", "Enhanced resume")
    else:
        session["resume_preview_message"] = (
            "We couldn't build an enhanced resume from the current data. "
            "Try uploading a fuller resume or updating your target role."
        )

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
        session["dashboard_notice_message"] = (
            "Analyze your resume first, then generate a cover letter from the preview page."
        )
        return redirect(url_for("main.dashboard"))

    enhanced_resume = session.get("enhanced_resume")

    draft = build_cover_letter(
        profile=report_data.get("profile"),
        tailored=report_data.get("tailored"),
        rewrite=report_data.get("rewrite"),
        match=report_data.get("match"),
        enhanced_resume=enhanced_resume,
        job_context=report_data.get("job_context"),
    )

    if draft:
        session["cover_letter_draft"] = draft
        set_last_action(session, "Cover letter generated")
        _record_activity(
            user_id,
            "cover_letter_generated",
            "Generated cover letter draft",
        )
        if not report_data.get("job_context"):
            session["resume_preview_message"] = (
                "This cover letter was generated without a selected job. "
                "Pick a job on the dashboard for a more targeted draft."
            )
    else:
        session["resume_preview_message"] = (
            "We couldn't generate a cover letter from the current data yet. "
            "Try enhancing your resume first or adding a target role."
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
        session["resume_preview_message"] = (
            "Generate a cover letter draft first, then enhance it."
        )
        return redirect(url_for("main.resume_preview"))

    enhanced_resume = session.get("enhanced_resume")
    report_data = session.get("report_data")
    enhanced_cl = enhance_cover_letter(
        draft,
        enhanced_resume,
        job_context=(report_data or {}).get("job_context"),
    )

    if enhanced_cl:
        session["enhanced_cover_letter"] = enhanced_cl
        set_last_action(session, "Cover letter enhanced")
        _record_activity(user_id, "cover_letter_enhanced", "Enhanced cover letter")
    else:
        session["resume_preview_message"] = (
            "We couldn't enhance this cover letter with the current data. "
            "Review the draft and try again after selecting a job."
        )

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

    # M105: wrap load in try/except so stale/corrupt packages degrade gracefully
    try:
        report_data, enhanced_resume, cl_draft, enhanced_cl = load_package(pkg)
    except Exception:
        logger.warning("Package %s failed to load; redirecting.", package_id)
        session["package_recovery_message"] = (
            "This application package could not be fully loaded. "
            "It may have been saved in an older format. "
            "Try preparing a new application from the dashboard."
        )
        return redirect(url_for("main.dashboard"))

    # M105: ensure report_data is at least a dict so downstream never crashes
    if not report_data or not isinstance(report_data, dict):
        report_data = {}
        session["resume_preview_message"] = (
            "This saved package only included partial data. Review what loaded here, "
            "then rebuild a fresh package from the dashboard if needed."
        )

    session["report_data"] = report_data
    session["enhanced_resume"] = enhanced_resume
    session["cover_letter_draft"] = cl_draft
    session["enhanced_cover_letter"] = enhanced_cl

    # M105: only refresh intelligence when report_data has content
    if report_data:
        _refresh_intelligence(report_data)

    # M100/M105: rehydrate selected-job intelligence from package context
    _rehydrate_selected_job(pkg, report_data)

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


def _rehydrate_selected_job(pkg, report_data):
    """M105: Safely restore selected-job intel/gap from a package.

    Uses package-embedded data first, falls back to job_context fields,
    and finally attempts regeneration via ``_selected_job_state()``.
    """
    job_ctx = (report_data or {}).get("job_context")
    if not job_ctx:
        session.pop("selected_job_intelligence", None)
        session.pop("selected_job_gap", None)
        return

    # Prefer package-level snapshots (M100), fall back to inline context
    intel = pkg.get("selected_job_intelligence") or job_ctx.get("intelligence")
    gap = pkg.get("selected_job_gap") or job_ctx.get("gap")

    if intel:
        session["selected_job_intelligence"] = intel
    if gap:
        session["selected_job_gap"] = gap

    # If still missing, regenerate on the fly
    if not intel or not gap:
        try:
            _selected_job_state()
        except Exception:
            logger.debug("_rehydrate_selected_job: regen failed", exc_info=True)


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

    # M73/M79/M85: Use job_context from dataset/external if available
    job_ctx = report_data.get("job_context") if report_data else None
    if job_ctx:
        job = create_saved_job(
            report_data=report_data,
            title=job_ctx.get("title"),
            company=job_ctx.get("company"),
            location=job_ctx.get("location"),
            session_data=session,
        )
        job["dataset_job_id"] = job_ctx.get("job_id")
        job["source"] = job_ctx.get("source", "internal")
        job["source_name"] = job_ctx.get("source_name")
        job["skills"] = job_ctx.get("skills", [])
        job["matched_skills"] = job_ctx.get("matched_skills", job_ctx.get("skills", []))
        job["missing_skills"] = job_ctx.get("missing_skills", [])
        job["url"] = job_ctx.get("url")
        job["apply_url"] = job_ctx.get("apply_url")
        job["posted_at"] = job_ctx.get("posted_at")
        job["freshness_score"] = job_ctx.get("freshness_score")
    else:
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

    # M74: Compute match info if job came from dataset
    job_match_info = None
    job_intel = None
    job_gap_info = None
    dataset_job = None
    if job.get("dataset_job_id"):
        dataset_job = find_job_by_id(job["dataset_job_id"])
        if dataset_job:
            report_data = session.get("report_data")
            profile = report_data.get("profile") if report_data else None
            resume_skills = {
                s.lower() for s in (profile.get("skills", []) if profile else [])
            }
            job_skills = {s.lower() for s in dataset_job.get("skills", [])}
            overlap = resume_skills & job_skills
            score = round(len(overlap) / len(job_skills) * 100) if job_skills else 0
            job_match_info = {
                "matched_skills": sorted(overlap),
                "score": score,
                "description": dataset_job.get("description", ""),
            }
            # M98: compute richer intelligence + gap
            job_intel = extract_job_intelligence(dataset_job)
            if report_data:
                job_gap_info = analyze_job_gap(report_data, dataset_job)

    return render_template(
        "job_detail.html",
        job=job,
        followup=followup,
        job_match_info=job_match_info,
        job_intel=job_intel,
        job_gap_info=job_gap_info,
        has_report_data=bool(session.get("report_data")),
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
        session["dashboard_notice_message"] = (
            "Analyze your resume first, then prepare a complete application package."
        )
        return redirect(url_for("main.dashboard"))

    # Step 2: Enhance resume if not done
    if not session.get("enhanced_resume"):
        enhanced = enhance_resume(
            profile=report_data.get("profile"),
            tailored=report_data.get("tailored"),
            rewrite=report_data.get("rewrite"),
            match=report_data.get("match"),
            job_context=report_data.get("job_context"),
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
            job_context=report_data.get("job_context"),
        )
        if draft:
            session["cover_letter_draft"] = draft

    # Step 4: Enhance cover letter if not done
    if not session.get("enhanced_cover_letter"):
        cl_draft = session.get("cover_letter_draft")
        if cl_draft:
            enhanced_cl = enhance_cover_letter(
                cl_draft,
                session.get("enhanced_resume"),
                job_context=report_data.get("job_context"),
            )
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

    if not report_data.get("job_context"):
        session["resume_preview_message"] = (
            "This application package was prepared without a selected job. "
            "Choose a job on the dashboard to add role-specific targeting and gap analysis."
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
    gate_return_to = session.pop("gate_return_to", None)
    # Don't show trial or elite as purchasable plans
    display_order = [t for t in TIER_ORDER if t not in ("trial", "elite")]
    return render_template(
        "pricing.html",
        tiers=TIER_CONFIG,
        tier_order=display_order,
        full_tier_order=TIER_ORDER,
        gate_message=gate_message,
        gate_return_to=gate_return_to,
        **_tier_ctx(),
    )


@main_bp.route("/upgrade/<tier_name>")
def upgrade(tier_name):
    if tier_name not in TIER_ORDER or tier_name == "trial":
        if tier_name == "trial":
            session["gate_message"] = (
                "Your 7-day trial starts automatically on first use. "
                "Choose a paid plan to keep premium workflows after it ends."
            )
        return redirect(url_for("main.pricing"))
    user_id = session.get("user_id")
    session["user_tier"] = tier_name
    persist_tier(user_id, tier_name)
    # M118: redirect back to where the user came from, if available
    return_to = request.args.get("return_to") or session.pop("gate_return_to", None)
    if return_to and return_to.startswith("/"):
        return redirect(return_to)
    return redirect(url_for("main.pricing"))


# ------------------------------------------------------------------
# Bundle V — Founder Metrics
# ------------------------------------------------------------------


@main_bp.route("/founder/metrics")
def founder_metrics():
    if not session.get("is_authenticated"):
        return redirect(url_for("main.login_page"))
    if not session.get("is_admin"):
        return "Forbidden", 403

    from sqlalchemy import func

    total_users = UserIdentity.query.count()
    total_signups = ActivityEvent.query.filter_by(event_type="signup_completed").count()
    users_with_resume = UserIdentity.query.filter(
        UserIdentity.has_uploaded_resume == True  # noqa: E712
    ).count()
    users_with_matches = UserIdentity.query.filter(
        UserIdentity.has_generated_matches == True  # noqa: E712
    ).count()
    onboarding_complete_count = UserIdentity.query.filter(
        UserIdentity.onboarding_completed_at.isnot(None)
    ).count()
    onboarding_pct = (
        round(onboarding_complete_count / total_users * 100, 1) if total_users else 0
    )

    seven_days_ago = datetime.utcnow() - __import__("datetime").timedelta(days=7)
    signups_7d = ActivityEvent.query.filter(
        ActivityEvent.event_type == "signup_completed",
        ActivityEvent.created_at >= seven_days_ago,
    ).count()
    events_7d = ActivityEvent.query.filter(
        ActivityEvent.created_at >= seven_days_ago,
    ).count()

    recent_events = (
        app_db.session.query(ActivityEvent, UserIdentity.email)
        .outerjoin(UserIdentity, ActivityEvent.user_id == UserIdentity.id)
        .order_by(ActivityEvent.created_at.desc())
        .limit(10)
        .all()
    )

    return render_template(
        "founder_metrics.html",
        total_users=total_users,
        total_signups=total_signups,
        users_with_resume=users_with_resume,
        users_with_matches=users_with_matches,
        onboarding_complete_count=onboarding_complete_count,
        onboarding_pct=onboarding_pct,
        signups_7d=signups_7d,
        events_7d=events_7d,
        recent_events=recent_events,
    )


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
# Auth — Signup / Login / Logout
# ------------------------------------------------------------------


@main_bp.route("/signup", methods=["GET", "POST"])
def signup_page():
    if session.get("is_authenticated"):
        return redirect(url_for("main.dashboard"))

    if request.method == "GET":
        return render_template("signup.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()

    error = None
    if not email or not password:
        error = "Email and password are required."
    elif len(password) < 6:
        error = "Password must be at least 6 characters."

    if error:
        return render_template("signup.html", error=error, email_value=email)

    try:
        existing = UserIdentity.query.filter_by(email=email).first()
        if existing:
            return render_template(
                "signup.html",
                error="An account with this email already exists.",
                email_value=email,
            )

        # Upgrade current anonymous session user if present
        user_id = session.get("user_id")
        user = None
        if user_id:
            user = UserIdentity.query.filter_by(id=user_id).first()

        if not user:
            user = UserIdentity()
            start_trial(user)
            app_db.session.add(user)

        user.email = email
        user.set_password(password)
        user.last_login_at = datetime.utcnow()
        app_db.session.commit()

        _sync_admin_flag(user)
        # Bundle W — sync paid status & log trial start
        if sync_paid_status(user):
            app_db.session.commit()
            _log_db_activity(user.id, "paid_access_granted", "Paid via env config")
        elif user.tier == "trial":
            _log_db_activity(user.id, "trial_started", "Trial started on signup")

        session["user_id"] = user.id
        session["is_authenticated"] = True
        session["current_user_email"] = email
        session["user_tier"] = user.tier or "free"
        session["is_admin"] = bool(getattr(user, "is_admin", False))

        days_left = trial_days_remaining(user)
        if days_left is not None:
            session["trial_days_left"] = days_left

        _log_event("signup", {"email": email})
        _log_db_activity(
            user.id, "signup_completed", "User signed up", {"email": email}
        )
        return redirect(url_for("main.dashboard"))
    except Exception as exc:
        app_db.session.rollback()
        logger.error("Signup error: %s", exc)
        return render_template(
            "signup.html",
            error="An error occurred. Please try again.",
            email_value=email,
        )


@main_bp.route("/login", methods=["GET", "POST"])
def login_page():
    if session.get("is_authenticated"):
        return redirect(url_for("main.dashboard"))

    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()

    if not email or not password:
        return render_template(
            "login.html",
            error="Email and password are required.",
            email_value=email,
        )

    try:
        user = UserIdentity.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            return render_template(
                "login.html",
                error="Invalid email or password.",
                email_value=email,
            )

        if hasattr(user, "is_active") and user.is_active is False:
            return render_template(
                "login.html",
                error="This account has been deactivated.",
                email_value=email,
            )

        # Update last_login_at
        user.last_login_at = datetime.utcnow()
        app_db.session.commit()

        _sync_admin_flag(user)
        # Bundle W — check trial expiry + sync paid status on login
        check_trial_expiry(user)
        if sync_paid_status(user):
            _log_db_activity(user.id, "paid_access_granted", "Paid via env config")
        app_db.session.commit()

        # Clear session and set authenticated user
        session.clear()
        session.permanent = True
        session["user_id"] = user.id
        session["is_authenticated"] = True
        session["current_user_email"] = email
        session["user_tier"] = user.tier or "free"
        session["is_admin"] = bool(getattr(user, "is_admin", False))

        days_left = trial_days_remaining(user)
        if days_left is not None:
            session["trial_days_left"] = days_left

        _log_event("login", {"email": email})
        _log_db_activity(user.id, "login_completed", "User logged in", {"email": email})
        return redirect(url_for("main.dashboard"))
    except Exception as exc:
        logger.error("Login error: %s", exc)
        return render_template(
            "login.html",
            error="An error occurred. Please try again.",
            email_value=email,
        )


@main_bp.route("/logout")
def logout():
    _log_event("logout")
    user_id = session.get("user_id")
    if user_id:
        _log_db_activity(user_id, "logout_completed", "User logged out")
    session.clear()
    return redirect(url_for("main.landing"))


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


# ------------------------------------------------------------------
# M72 — Job Match Route
# ------------------------------------------------------------------


@main_bp.route("/job-match/<job_id>")
def job_match(job_id):
    """Inject a dataset/external job into session context, then prepare application."""
    blocked = _gate("prepare_application")
    if blocked:
        return blocked

    # Try internal dataset first, then search unified feed for external jobs
    job = find_job_by_id(job_id)
    if not job:
        # Check unified feed (may be an external job)
        unified = get_unified_jobs()
        job = next((j for j in unified if j.get("id") == job_id), None)
    if not job:
        return redirect(url_for("main.dashboard"))

    report_data = session.get("report_data")
    if not report_data:
        return redirect(url_for("main.dashboard"))

    # Inject job context into report_data for the prepare-application flow
    if not report_data.get("match"):
        report_data["match"] = {}
    report_data["match"]["target_role"] = job["title"]

    # Compute match info for this specific job (M79/M85)
    match_result = match_jobs(report_data, jobs=[job], limit=1)
    matched_skills = match_result[0]["matched_skills"] if match_result else []
    missing_skills = match_result[0]["missing_skills"] if match_result else []
    freshness_score = match_result[0].get("freshness_score") if match_result else None

    report_data["job_context"] = {
        "job_id": job["id"],
        "title": job["title"],
        "company": job["company"],
        "location": job.get("location", ""),
        "description": job.get("description", ""),
        "skills": job.get("skills", []),
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "source": job.get("source", "internal"),
        "source_name": job.get("source_name"),
        "url": job.get("url"),
        "apply_url": job.get("apply_url"),
        "posted_at": job.get("posted_at"),
        "freshness_score": freshness_score,
    }
    session["report_data"] = report_data

    # M95: Compute and store job intelligence + gap analysis
    job_intel = extract_job_intelligence(job)
    job_gap = analyze_job_gap(report_data, job)
    session["selected_job_intelligence"] = job_intel
    session["selected_job_gap"] = job_gap
    report_data["job_context"]["intelligence"] = job_intel
    report_data["job_context"]["gap"] = job_gap
    session["report_data"] = report_data

    _log_event("job_match_clicked", {"job_id": job_id})
    return redirect(url_for("main.prepare_application"))


# ------------------------------------------------------------------
# M89 — Apply Pipeline Route
# ------------------------------------------------------------------


@main_bp.route("/apply/<job_id>")
def apply_job(job_id):
    """Redirect user to external apply URL and record analytics."""
    user_id = session.get("user_id")

    # Resolve the job from unified feed
    job = find_job_by_id(job_id)
    if not job:
        unified = get_unified_jobs(limit=200)
        job = next((j for j in unified if j.get("id") == job_id), None)
    if not job:
        return redirect(url_for("main.dashboard"))

    apply_url = job.get("apply_url") or job.get("url")
    if not apply_url:
        return redirect(url_for("main.dashboard"))

    _record_activity(
        user_id,
        "job_applied",
        "Applied to: %s at %s" % (job.get("title", ""), job.get("company", "")),
    )
    _log_event(
        "apply_clicked",
        {"job_id": job_id, "source": job.get("source", ""), "url": apply_url},
    )
    return redirect(apply_url)


@main_bp.route("/<path:path>")
def fallback(path):
    return redirect(url_for("main.dashboard"))
