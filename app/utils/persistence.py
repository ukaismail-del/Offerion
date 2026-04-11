"""M47 — Persistence Layer.

Bridges session-based utils and the database. Every function fails
gracefully — if the DB is unavailable, session data is still used.
"""

import json
import logging

from app.db import db
from app.models import (
    SavedJob,
    ResumeVersion,
    ApplicationPackage,
    Alert,
    ActivityEvent,
    UserIdentity,
)

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Saved Jobs
# ------------------------------------------------------------------


def persist_job(user_id, job_dict):
    """Save a job dict to the database. Returns the DB record or None."""
    try:
        rec = SavedJob(
            id=job_dict["id"],
            user_id=user_id,
            title=job_dict.get("title", ""),
            company=job_dict.get("company", ""),
            location=job_dict.get("location", ""),
            job_url=job_dict.get("job_url", ""),
            notes=job_dict.get("notes", ""),
            source=job_dict.get("source", ""),
            status=job_dict.get("status", "Saved"),
        )
        db.session.add(rec)
        db.session.commit()
        return rec
    except Exception as exc:
        db.session.rollback()
        logger.warning("persist_job failed: %s", exc)
        return None


def persist_job_status(user_id, job_id, new_status):
    """Update job status in DB."""
    try:
        rec = SavedJob.query.filter_by(id=job_id, user_id=user_id).first()
        if rec:
            rec.status = new_status
            db.session.commit()
            return True
    except Exception as exc:
        db.session.rollback()
        logger.warning("persist_job_status failed: %s", exc)
    return False


def remove_job(user_id, job_id):
    """Delete a job from the database."""
    try:
        rec = SavedJob.query.filter_by(id=job_id, user_id=user_id).first()
        if rec:
            db.session.delete(rec)
            db.session.commit()
            return True
    except Exception as exc:
        db.session.rollback()
        logger.warning("remove_job failed: %s", exc)
    return False


def load_jobs(user_id):
    """Load all saved jobs for a user. Returns list of dicts."""
    try:
        recs = (
            SavedJob.query.filter_by(user_id=user_id)
            .order_by(SavedJob.created_at)
            .all()
        )
        return [r.to_dict() for r in recs]
    except Exception as exc:
        logger.warning("load_jobs failed: %s", exc)
        return None


# ------------------------------------------------------------------
# Resume Versions
# ------------------------------------------------------------------


def persist_version(user_id, version_dict):
    """Save a resume version dict to the database."""
    try:
        rec = ResumeVersion(
            id=version_dict["id"],
            user_id=user_id,
            label=version_dict.get("label", ""),
            target_title=version_dict.get("target_title", ""),
            report_data_json=json.dumps(version_dict.get("report_data", {})),
            enhanced_resume_json=json.dumps(version_dict.get("enhanced_resume")),
        )
        db.session.add(rec)
        db.session.commit()
        return rec
    except Exception as exc:
        db.session.rollback()
        logger.warning("persist_version failed: %s", exc)
        return None


def remove_version(user_id, version_id):
    """Delete a resume version from the database."""
    try:
        rec = ResumeVersion.query.filter_by(id=version_id, user_id=user_id).first()
        if rec:
            db.session.delete(rec)
            db.session.commit()
            return True
    except Exception as exc:
        db.session.rollback()
        logger.warning("remove_version failed: %s", exc)
    return False


def load_versions(user_id):
    """Load all resume versions for a user."""
    try:
        recs = (
            ResumeVersion.query.filter_by(user_id=user_id)
            .order_by(ResumeVersion.created_at)
            .all()
        )
        return [r.to_dict() for r in recs]
    except Exception as exc:
        logger.warning("load_versions failed: %s", exc)
        return None


# ------------------------------------------------------------------
# Application Packages
# ------------------------------------------------------------------


def persist_package(user_id, pkg_dict):
    """Save an application package to the database."""
    try:
        rec = ApplicationPackage(
            id=pkg_dict["id"],
            user_id=user_id,
            label=pkg_dict.get("label", ""),
            target_title=pkg_dict.get("target_title", ""),
            company=pkg_dict.get("company", ""),
            report_data_json=json.dumps(pkg_dict.get("report_data", {})),
            enhanced_resume_json=json.dumps(pkg_dict.get("enhanced_resume")),
            cover_letter_draft_json=json.dumps(pkg_dict.get("cover_letter_draft")),
            enhanced_cover_letter_json=json.dumps(
                pkg_dict.get("enhanced_cover_letter")
            ),
        )
        db.session.add(rec)
        db.session.commit()
        return rec
    except Exception as exc:
        db.session.rollback()
        logger.warning("persist_package failed: %s", exc)
        return None


def remove_package(user_id, package_id):
    """Delete an application package from the database."""
    try:
        rec = ApplicationPackage.query.filter_by(id=package_id, user_id=user_id).first()
        if rec:
            db.session.delete(rec)
            db.session.commit()
            return True
    except Exception as exc:
        db.session.rollback()
        logger.warning("remove_package failed: %s", exc)
    return False


def load_packages(user_id):
    """Load all application packages for a user."""
    try:
        recs = (
            ApplicationPackage.query.filter_by(user_id=user_id)
            .order_by(ApplicationPackage.created_at)
            .all()
        )
        return [r.to_dict() for r in recs]
    except Exception as exc:
        logger.warning("load_packages failed: %s", exc)
        return None


# ------------------------------------------------------------------
# Alerts (M49)
# ------------------------------------------------------------------


def persist_alert(user_id, alert_dict):
    """Save an alert to the database."""
    try:
        rec = Alert(
            id=alert_dict["id"],
            user_id=user_id,
            job_id=alert_dict.get("job_id", ""),
            alert_type=alert_dict.get("type", "follow_up"),
            message=alert_dict.get("message", ""),
            due_at=alert_dict.get("due_at", ""),
            is_complete=alert_dict.get("is_complete", False),
        )
        db.session.add(rec)
        db.session.commit()
        return rec
    except Exception as exc:
        db.session.rollback()
        logger.warning("persist_alert failed: %s", exc)
        return None


def persist_alert_complete(user_id, alert_id):
    """Mark an alert as complete in the database."""
    try:
        rec = Alert.query.filter_by(id=alert_id, user_id=user_id).first()
        if rec:
            rec.is_complete = True
            db.session.commit()
            return True
    except Exception as exc:
        db.session.rollback()
        logger.warning("persist_alert_complete failed: %s", exc)
    return False


def remove_alert(user_id, alert_id):
    """Delete an alert from the database."""
    try:
        rec = Alert.query.filter_by(id=alert_id, user_id=user_id).first()
        if rec:
            db.session.delete(rec)
            db.session.commit()
            return True
    except Exception as exc:
        db.session.rollback()
        logger.warning("remove_alert failed: %s", exc)
    return False


def remove_alerts_for_job(user_id, job_id):
    """Delete all alerts tied to a job."""
    try:
        Alert.query.filter_by(user_id=user_id, job_id=job_id).delete()
        db.session.commit()
        return True
    except Exception as exc:
        db.session.rollback()
        logger.warning("remove_alerts_for_job failed: %s", exc)
    return False


def load_alerts(user_id):
    """Load all alerts for a user."""
    try:
        recs = Alert.query.filter_by(user_id=user_id).order_by(Alert.due_at).all()
        return [r.to_dict() for r in recs]
    except Exception as exc:
        logger.warning("load_alerts failed: %s", exc)
        return None


# ------------------------------------------------------------------
# Activity Events (M49)
# ------------------------------------------------------------------


def persist_event(user_id, event_dict):
    """Save an activity event to the database."""
    try:
        rec = ActivityEvent(
            id=event_dict.get("id", "")[:12],
            user_id=user_id,
            event_type=event_dict.get("event_type", ""),
            label=event_dict.get("label", ""),
            meta_json=json.dumps(event_dict.get("meta", {})),
        )
        db.session.add(rec)
        db.session.commit()
        return rec
    except Exception as exc:
        db.session.rollback()
        logger.warning("persist_event failed: %s", exc)
        return None


def load_events(user_id, limit=30):
    """Load recent activity events for a user (latest first)."""
    try:
        recs = (
            ActivityEvent.query.filter_by(user_id=user_id)
            .order_by(ActivityEvent.created_at.desc())
            .limit(limit)
            .all()
        )
        return [r.to_dict() for r in recs]
    except Exception as exc:
        logger.warning("load_events failed: %s", exc)
        return None


# ------------------------------------------------------------------
# Sync helpers: hydrate session from DB
# ------------------------------------------------------------------


def hydrate_session_from_db(session_obj, user_id):
    """Load persisted records into the session (if not already present).

    Called once per request/page-load so the dashboard reflects
    persisted data even after a session reset.
    """
    try:
        # Saved jobs
        if "saved_jobs" not in session_obj or not session_obj["saved_jobs"]:
            db_jobs = load_jobs(user_id)
            if db_jobs is not None:
                session_obj["saved_jobs"] = db_jobs

        # Resume versions
        if "resume_versions" not in session_obj or not session_obj["resume_versions"]:
            db_versions = load_versions(user_id)
            if db_versions is not None:
                session_obj["resume_versions"] = db_versions

        # Application packages
        if (
            "application_packages" not in session_obj
            or not session_obj["application_packages"]
        ):
            db_packages = load_packages(user_id)
            if db_packages is not None:
                session_obj["application_packages"] = db_packages

        # Alerts
        if "alerts" not in session_obj or not session_obj["alerts"]:
            db_alerts = load_alerts(user_id)
            if db_alerts is not None:
                session_obj["alerts"] = db_alerts

        # Activity timeline
        if (
            "activity_timeline" not in session_obj
            or not session_obj["activity_timeline"]
        ):
            db_events = load_events(user_id, limit=30)
            if db_events is not None:
                session_obj["activity_timeline"] = db_events

    except Exception as exc:
        logger.warning("hydrate_session_from_db failed: %s", exc)


# ------------------------------------------------------------------
# Tier Persistence (M54)
# ------------------------------------------------------------------


def persist_tier(user_id, tier_name):
    """Update the user's tier in the database."""
    try:
        rec = UserIdentity.query.filter_by(id=user_id).first()
        if rec:
            rec.tier = tier_name
            db.session.commit()
            return True
    except Exception as exc:
        db.session.rollback()
        logger.warning("persist_tier failed: %s", exc)
    return False


def load_tier(user_id):
    """Load the user's tier from the database. Returns tier string or None."""
    try:
        rec = UserIdentity.query.filter_by(id=user_id).first()
        if rec:
            return rec.tier or "free"
    except Exception as exc:
        logger.warning("load_tier failed: %s", exc)
    return None
