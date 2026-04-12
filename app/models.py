"""M46 — Database Models.

Lean models for persistent Offerion records. Nested data stored as JSON text.
"""

import json
import uuid
from datetime import datetime

from werkzeug.security import generate_password_hash, check_password_hash

from app.db import db


def _new_id():
    return uuid.uuid4().hex[:12]


def _now():
    return datetime.utcnow()


class UserIdentity(db.Model):
    """M48 — Persistent user identity with optional authentication."""

    __tablename__ = "user_identity"

    id = db.Column(db.String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    tier = db.Column(db.String(20), default="trial")
    created_at = db.Column(db.DateTime, default=_now)

    # Auth fields
    email = db.Column(db.String(255), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(256), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)
    email_verified = db.Column(db.Boolean, default=False)
    email_verification_token_hash = db.Column(db.String(255), nullable=True)
    email_verification_expires_at = db.Column(db.DateTime, nullable=True)
    email_verified_at = db.Column(db.DateTime, nullable=True)
    password_reset_token_hash = db.Column(db.String(255), nullable=True)
    password_reset_expires_at = db.Column(db.DateTime, nullable=True)
    password_reset_requested_at = db.Column(db.DateTime, nullable=True)

    # Login tracking
    last_login_at = db.Column(db.DateTime, nullable=True)

    # Onboarding tracking
    has_uploaded_resume = db.Column(db.Boolean, default=False)
    has_generated_matches = db.Column(db.Boolean, default=False)
    onboarding_completed_at = db.Column(db.DateTime, nullable=True)

    # Trial tracking
    trial_start = db.Column(db.DateTime, nullable=True)
    trial_end = db.Column(db.DateTime, nullable=True)

    # Usage tracking
    daily_matches_used = db.Column(db.Integer, default=0)
    last_usage_reset = db.Column(db.DateTime, nullable=True)

    # Bundle W — Plan enforcement fields
    subscription_status = db.Column(db.String(20), nullable=True)  # 'active' | None
    paid_started_at = db.Column(db.DateTime, nullable=True)
    monthly_resume_analyses_used = db.Column(db.Integer, default=0)
    monthly_job_views_used = db.Column(db.Integer, default=0)
    monthly_resume_downloads_used = db.Column(db.Integer, default=0)
    usage_reset_at = db.Column(db.DateTime, nullable=True)
    hard_gated_at = db.Column(db.DateTime, nullable=True)
    last_upgrade_prompt_at = db.Column(db.DateTime, nullable=True)

    # Bundle T — Stripe integration fields
    stripe_customer_id = db.Column(db.String(100), nullable=True)
    stripe_subscription_id = db.Column(db.String(100), nullable=True)

    # relationships
    saved_jobs = db.relationship("SavedJob", backref="user", lazy=True)
    resume_versions = db.relationship("ResumeVersion", backref="user", lazy=True)
    application_packages = db.relationship(
        "ApplicationPackage", backref="user", lazy=True
    )
    alerts = db.relationship("Alert", backref="user", lazy=True)
    activity_events = db.relationship("ActivityEvent", backref="user", lazy=True)

    def set_password(self, password):
        """Hash and store a password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verify a password against the stored hash."""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)


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
    event_type = db.Column(db.String(60), default="", index=True)
    label = db.Column(db.String(300), default="")
    event_label = db.Column(db.String(300), nullable=True)
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


# ------------------------------------------------------------------
# Bundle T — Server-side heavy-state persistence
# ------------------------------------------------------------------


class UserState(db.Model):
    """Server-side storage for heavy session data (report_data, resume_text).

    One row per user.  Replaces session cookie storage for large blobs
    to avoid hitting cookie size limits (~4 KB).
    """

    __tablename__ = "user_state"

    user_id = db.Column(
        db.String(36), db.ForeignKey("user_identity.id"), primary_key=True
    )
    report_data_json = db.Column(db.Text, default="{}")
    resume_text = db.Column(db.Text, default="")
    enhanced_resume_json = db.Column(db.Text, default="null")
    cover_letter_draft_json = db.Column(db.Text, default="null")
    enhanced_cover_letter_json = db.Column(db.Text, default="null")
    selected_job_intel_json = db.Column(db.Text, default="null")
    selected_job_gap_json = db.Column(db.Text, default="null")
    recommended_jobs_json = db.Column(db.Text, default="{}")
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now)


# ------------------------------------------------------------------
# Bundle T — Shared report durability
# ------------------------------------------------------------------


class SharedReport(db.Model):
    """Durable shared-report snapshot (survives logout/session reset)."""

    __tablename__ = "shared_report"

    id = db.Column(db.String(12), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey("user_identity.id"), nullable=True)
    snapshot_json = db.Column(db.Text, default="{}")
    created_at = db.Column(db.DateTime, default=_now)
