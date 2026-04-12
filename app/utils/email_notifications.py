"""Bundle V — Email notification delivery foundation.

Uses SMTP when configured, otherwise degrades cleanly to logged no-op
behavior so reminder workflows never break user actions.
"""

import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)


class EmailNotificationService:
    """Lightweight email service stub.

    Usage::

        svc = EmailNotificationService()
        svc.send_alert_reminder(email, alert)
        svc.send_welcome(email, user_name)
    """

    def __init__(self, sender=None, enabled=None):
        self.default_sender = sender or "noreply@offerion.onrender.com"
        self.enabled_override = enabled

    def get_config(self):
        """Return the current email delivery configuration and health."""
        host = os.environ.get("OFFERION_SMTP_HOST", "").strip()
        port_raw = os.environ.get("OFFERION_SMTP_PORT", "587").strip() or "587"
        username = os.environ.get("OFFERION_SMTP_USERNAME", "").strip()
        password = os.environ.get("OFFERION_SMTP_PASSWORD", "")
        sender = (
            os.environ.get("OFFERION_SMTP_FROM_EMAIL", "").strip()
            or self.default_sender
        )
        use_tls = os.environ.get("OFFERION_SMTP_USE_TLS", "1").strip().lower() not in (
            "0",
            "false",
            "no",
        )

        missing = []
        if not host:
            missing.append("OFFERION_SMTP_HOST")
        try:
            port = int(port_raw)
        except ValueError:
            port = 587
            missing.append("OFFERION_SMTP_PORT")

        if (username and not password) or (password and not username):
            missing.extend(
                [
                    key
                    for key, value in (
                        ("OFFERION_SMTP_USERNAME", username),
                        ("OFFERION_SMTP_PASSWORD", password),
                    )
                    if not value
                ]
            )

        env_enabled = os.environ.get("OFFERION_EMAIL_ENABLED", "1").strip().lower() not in (
            "0",
            "false",
            "no",
        )
        enabled = self.enabled_override if self.enabled_override is not None else env_enabled
        configured = enabled and not missing

        return {
            "enabled": configured,
            "requested": enabled,
            "mode": "smtp" if configured else "log-only",
            "host": host,
            "port": port,
            "username": username,
            "password": password,
            "sender": sender,
            "use_tls": use_tls,
            "missing": missing,
            "reason": None if configured else (
                "email disabled by configuration"
                if not enabled
                else "missing SMTP configuration"
            ),
        }

    # ── Internal ──────────────────────────────────────────────────

    def _send(self, to, subject, body):
        """Deliver an email and return a structured result dict."""
        config = self.get_config()
        if not to:
            logger.warning("Email skipped: missing recipient for subject=%s", subject)
            return {
                "success": False,
                "status": "skipped",
                "reason": "missing recipient",
                "mode": config["mode"],
            }

        if not config["enabled"]:
            logger.info(
                "Email not sent (%s): to=%s subject=%s missing=%s",
                config["reason"],
                to,
                subject,
                ",".join(config["missing"]),
            )
            return {
                "success": False,
                "status": "skipped",
                "reason": config["reason"],
                "missing": config["missing"],
                "mode": config["mode"],
            }

        message = EmailMessage()
        message["From"] = config["sender"]
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)

        try:
            with smtplib.SMTP(config["host"], config["port"], timeout=15) as smtp:
                smtp.ehlo()
                if config["use_tls"]:
                    smtp.starttls()
                    smtp.ehlo()
                if config["username"]:
                    smtp.login(config["username"], config["password"])
                smtp.send_message(message)
            logger.info("Email sent: to=%s subject=%s", to, subject)
            return {"success": True, "status": "sent", "mode": config["mode"]}
        except Exception as exc:
            logger.warning("Email send failed: to=%s subject=%s error=%s", to, subject, exc)
            return {
                "success": False,
                "status": "failed",
                "reason": str(exc),
                "mode": config["mode"],
            }

    # ── Public API ────────────────────────────────────────────────

    def send_welcome(self, to_email, user_name=None):
        """Welcome email after signup."""
        name = user_name or "there"
        return self._send(
            to=to_email,
            subject="Welcome to Offerion",
            body=(
                f"Hi {name},\n\n"
                "Welcome to Offerion!  Upload your resume to get started.\n\n"
                "— The Offerion Team"
            ),
        )

    def send_alert_reminder(self, to_email, alert):
        """Reminder email for an upcoming alert/follow-up."""
        message = alert.get("message", "You have an upcoming reminder")
        due = alert.get("due_at", "soon")
        return self._send(
            to=to_email,
            subject=f"Offerion Reminder: {message}",
            body=(
                f"Reminder: {message}\n"
                f"Due: {due}\n\n"
                "Log in to Offerion to take action.\n\n"
                "— The Offerion Team"
            ),
        )

    def send_trial_expiry_warning(self, to_email, days_left):
        """Warn user their trial is expiring soon."""
        return self._send(
            to=to_email,
            subject=f"Your Offerion trial ends in {days_left} day(s)",
            body=(
                f"Your 7-day trial ends in {days_left} day(s).\n\n"
                "Upgrade now to keep all premium features active.\n\n"
                "— The Offerion Team"
            ),
        )

    def send_upgrade_confirmation(self, to_email, tier_label):
        """Confirm a plan upgrade."""
        return self._send(
            to=to_email,
            subject=f"You're now on Offerion {tier_label}",
            body=(
                f"Your plan has been upgraded to {tier_label}.\n\n"
                "All premium features are now unlocked.  Head to your "
                "dashboard to continue.\n\n"
                "— The Offerion Team"
            ),
        )

    def health_summary(self):
        """Return a compact founder-facing health summary."""
        config = self.get_config()
        return {
            "enabled": config["enabled"],
            "mode": config["mode"],
            "sender": config["sender"],
            "missing": config["missing"],
            "reason": config["reason"],
        }


# Singleton for easy import
email_service = EmailNotificationService()
