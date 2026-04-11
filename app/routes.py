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

    return render_template(
        "resume_preview.html",
        profile=profile,
        tailored=tailored,
        rewrite=rewrite,
        target_title=target_title,
        skills_list=skills_list,
        education_list=education_list,
        enhanced=enhanced,
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


@main_bp.route("/<path:path>")
def fallback(path):
    return redirect(url_for("main.index"))
