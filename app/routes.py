import logging
import os

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
from app.utils.storage import save_file, delete_file

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

                            session["report_data"] = {
                                "result": result,
                                "profile": profile,
                                "match": match,
                                "suggestions": suggestions,
                                "feedback": feedback,
                                "jd_comparison": jd_comparison,
                                "rewrite": rewrite,
                            }
                            logger.info("Analysis complete for: %s", filename)
                    except Exception as exc:
                        logger.error("Error processing %s: %s", filename, exc)
                        error = "An error occurred while processing the file. Please try again."
                    finally:
                        delete_file(filepath)

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
    )

    return Response(
        report_text,
        mimetype="text/plain",
        headers={"Content-Disposition": "attachment; filename=offerion_report.txt"},
    )


@main_bp.route("/<path:path>")
def fallback(path):
    return redirect(url_for("main.index"))
