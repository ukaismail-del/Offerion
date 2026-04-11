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

logger = logging.getLogger(__name__)

main_bp = Blueprint("main", __name__)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@main_bp.route("/", methods=["GET", "POST"])
def index():
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

                            logger.info("Analysis complete for: %s", filename)
                    except Exception as exc:
                        logger.error("Error processing %s: %s", filename, exc)
                        error = "An error occurred while processing the file. Please try again."
                    finally:
                        delete_file(filepath)

    history = session.get("history", [])
    resume_versions = session.get("resume_versions", [])
    application_packages = session.get("application_packages", [])

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
        return redirect(url_for("main.index"))

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
    )


@main_bp.route("/enhance-resume")
def enhance_resume_route():
    report_data = session.get("report_data")
    if not report_data:
        return redirect(url_for("main.index"))

    enhanced = enhance_resume(
        profile=report_data.get("profile"),
        tailored=report_data.get("tailored"),
        rewrite=report_data.get("rewrite"),
        match=report_data.get("match"),
    )

    if enhanced:
        session["enhanced_resume"] = enhanced

    return redirect(url_for("main.resume_preview"))


@main_bp.route("/save-resume-version")
def save_resume_version():
    version = save_version(session)
    if not version:
        return redirect(url_for("main.index"))

    versions = session.get("resume_versions", [])
    versions.append(version)
    session["resume_versions"] = versions

    return redirect(url_for("main.resume_preview"))


@main_bp.route("/resume-version/<version_id>")
def open_resume_version(version_id):
    versions = session.get("resume_versions", [])
    version = find_version(versions, version_id)
    if not version:
        return redirect(url_for("main.index"))

    report_data, enhanced = load_version(version)
    session["report_data"] = report_data
    session["enhanced_resume"] = enhanced

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
    versions = session.get("resume_versions", [])
    session["resume_versions"] = delete_version(versions, version_id)
    return redirect(url_for("main.index"))


# ------------------------------------------------------------------
# M26 — Cover Letter Draft
# ------------------------------------------------------------------

@main_bp.route("/generate-cover-letter")
def generate_cover_letter_route():
    report_data = session.get("report_data")
    if not report_data:
        return redirect(url_for("main.index"))

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

    return redirect(url_for("main.resume_preview"))


# ------------------------------------------------------------------
# M27 — Cover Letter Enhancement
# ------------------------------------------------------------------

@main_bp.route("/enhance-cover-letter")
def enhance_cover_letter_route():
    draft = session.get("cover_letter_draft")
    if not draft:
        return redirect(url_for("main.resume_preview"))

    enhanced_resume = session.get("enhanced_resume")
    enhanced_cl = enhance_cover_letter(draft, enhanced_resume)

    if enhanced_cl:
        session["enhanced_cover_letter"] = enhanced_cl

    return redirect(url_for("main.resume_preview"))


# ------------------------------------------------------------------
# M28 — Application Package Download
# ------------------------------------------------------------------

@main_bp.route("/download-application-package")
def download_application_package():
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


def _build_application_package_text(report_data, enhanced_resume,
                                     cover_letter_draft, enhanced_cl):
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
    lines.append("SECTION 1 — RESUME")
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
    lines.append("SECTION 2 — COVER LETTER")
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
# M29 — Application Package Versioning
# ------------------------------------------------------------------

@main_bp.route("/save-application-package")
def save_application_package_route():
    pkg = save_package(session)
    if not pkg:
        return redirect(url_for("main.index"))

    packages = session.get("application_packages", [])
    packages.append(pkg)
    session["application_packages"] = packages

    return redirect(url_for("main.resume_preview"))


@main_bp.route("/application-package/<package_id>")
def open_application_package(package_id):
    packages = session.get("application_packages", [])
    pkg = find_package(packages, package_id)
    if not pkg:
        return redirect(url_for("main.index"))

    report_data, enhanced_resume, cl_draft, enhanced_cl = load_package(pkg)
    session["report_data"] = report_data
    session["enhanced_resume"] = enhanced_resume
    session["cover_letter_draft"] = cl_draft
    session["enhanced_cover_letter"] = enhanced_cl

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
    packages = session.get("application_packages", [])
    session["application_packages"] = delete_package(packages, package_id)
    return redirect(url_for("main.index"))


@main_bp.route("/<path:path>")
def fallback(path):
    return redirect(url_for("main.index"))
