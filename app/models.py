"""M46 — Database Models.

Lean models for persistent Offerion records. Nested data stored as JSON text.
"""

import json
import uuid
from datetime import datetime

from app.db import db


def _new_id():
    return uuid.uuid4().hex[:12]


def _now():
    return datetime.utcnow()


class UserIdentity(db.Model):
    """M48 — Anonymous persistent user identity."""

    __tablename__ = "user_identity"

    id = db.Column(db.String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    created_at = db.Column(db.DateTime, default=_now)

    # relationships
    saved_jobs = db.relationship("SavedJob", backref="user", lazy=True)
    resume_versions = db.relationship("ResumeVersion", backref="user", lazy=True)
    application_packages = db.relationship(
        "ApplicationPackage", backref="user", lazy=True
    )
    alerts = db.relationship("Alert", backref="user", lazy=True)
    activity_events = db.relationship("ActivityEvent", backref="user", lazy=True)


class SavedJob(db.Model):
    """Persistent saved job record."""

    __tablename__ = "saved_job"

    id = db.Column(db.String(12), primary_key=True, default=_new_id)
    user_id = db.Column(
        db.String(36), db.ForeignKey("user_identity.id"), nullable=False
    )
    title = db.Column(db.String(200), default="Untitled Role")
    company = db.Column(db.String(200), default="Unknown Company")
    location = db.Column(db.String(200), default="")
    job_url = db.Column(db.String(500), default="")
    notes = db.Column(db.Text, default="")
    source = db.Column(db.String(100), default="")
    status = db.Column(db.String(30), default="Saved")
    created_at = db.Column(db.DateTime, default=_now)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "job_url": self.job_url,
            "notes": self.notes,
            "source": self.source,
            "status": self.status,
            "created_at": (
                self.created_at.strftime("%Y-%m-%d %H:%M") if self.created_at else ""
            ),
        }


class ResumeVersion(db.Model):
    """Persistent resume version snapshot. Report data stored as JSON blob."""

    __tablename__ = "resume_version"

    id = db.Column(db.String(12), primary_key=True, default=_new_id)
    user_id = db.Column(
        db.String(36), db.ForeignKey("user_identity.id"), nullable=False
    )
    label = db.Column(db.String(200), default="")
    target_title = db.Column(db.String(200), default="")
    report_data_json = db.Column(db.Text, default="{}")
    enhanced_resume_json = db.Column(db.Text, default="null")
    created_at = db.Column(db.DateTime, default=_now)

    def to_dict(self):
        return {
            "id": self.id,
            "label": self.label,
            "target_title": self.target_title,
            "created_at": (
                self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else ""
            ),
            "report_data": (
                json.loads(self.report_data_json) if self.report_data_json else {}
            ),
            "enhanced_resume": (
                json.loads(self.enhanced_resume_json)
                if self.enhanced_resume_json
                else None
            ),
        }


class ApplicationPackage(db.Model):
    """Persistent application package snapshot."""

    __tablename__ = "application_package"

    id = db.Column(db.String(12), primary_key=True, default=_new_id)
    user_id = db.Column(
        db.String(36), db.ForeignKey("user_identity.id"), nullable=False
    )
    label = db.Column(db.String(200), default="")
    target_title = db.Column(db.String(200), default="")
    company = db.Column(db.String(200), default="")
    report_data_json = db.Column(db.Text, default="{}")
    enhanced_resume_json = db.Column(db.Text, default="null")
    cover_letter_draft_json = db.Column(db.Text, default="null")
    enhanced_cover_letter_json = db.Column(db.Text, default="null")
    created_at = db.Column(db.DateTime, default=_now)

    def to_dict(self):
        return {
            "id": self.id,
            "label": self.label,
            "target_title": self.target_title,
            "company": self.company,
            "created_at": (
                self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else ""
            ),
            "report_data": (
                json.loads(self.report_data_json) if self.report_data_json else {}
            ),
            "enhanced_resume": (
                json.loads(self.enhanced_resume_json)
                if self.enhanced_resume_json
                else None
            ),
            "cover_letter_draft": (
                json.loads(self.cover_letter_draft_json)
                if self.cover_letter_draft_json
                else None
            ),
            "enhanced_cover_letter": (
                json.loads(self.enhanced_cover_letter_json)
                if self.enhanced_cover_letter_json
                else None
            ),
        }


class Alert(db.Model):
    """Persistent alert / reminder."""

    __tablename__ = "alert"

    id = db.Column(db.String(12), primary_key=True, default=_new_id)
    user_id = db.Column(
        db.String(36), db.ForeignKey("user_identity.id"), nullable=False
    )
    job_id = db.Column(db.String(12), default="")
    alert_type = db.Column(db.String(30), default="follow_up")
    message = db.Column(db.String(500), default="")
    due_at = db.Column(db.String(20), default="")
    is_complete = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=_now)

    def to_dict(self):
        return {
            "id": self.id,
            "job_id": self.job_id,
            "type": self.alert_type,
            "message": self.message,
            "due_at": self.due_at,
            "is_complete": self.is_complete,
            "created_at": (
                self.created_at.strftime("%Y-%m-%d %H:%M") if self.created_at else ""
            ),
        }


class ActivityEvent(db.Model):
    """Persistent activity timeline event."""

    __tablename__ = "activity_event"

    id = db.Column(db.String(12), primary_key=True, default=_new_id)
    user_id = db.Column(
        db.String(36), db.ForeignKey("user_identity.id"), nullable=False
    )
    event_type = db.Column(db.String(60), default="")
    label = db.Column(db.String(300), default="")
    meta_json = db.Column(db.Text, default="{}")
    created_at = db.Column(db.DateTime, default=_now)

    def to_dict(self):
        return {
            "id": self.id,
            "event_type": self.event_type,
            "label": self.label,
            "created_at": (
                self.created_at.strftime("%Y-%m-%d %H:%M") if self.created_at else ""
            ),
            "meta": json.loads(self.meta_json) if self.meta_json else {},
        }
