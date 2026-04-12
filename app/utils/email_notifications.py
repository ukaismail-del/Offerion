"""Bundle U — Email Notification Service (Placeholder).

Clean integration point for future email delivery.  Currently logs
messages instead of sending them.  Replace ``_send`` with a real
provider (SendGrid, SES, etc.) when ready.
"""

import logging

logger = logging.getLogger(__name__)


class EmailNotificationService:
    """Lightweight email service stub.

    Usage::

        svc = EmailNotificationService()
        svc.send_alert_reminder(email, alert)
        svc.send_welcome(email, user_name)
    """

    def __init__(self, sender=None, enabled=False):
        self.sender = sender or "noreply@offerion.onrender.com"
        self.enabled = enabled

    # ── Internal ──────────────────────────────────────────────────

    def _send(self, to, subject, body):
        """Deliver an email.  Currently a no-op placeholder."""
        if not self.enabled:
            logger.info(
                "Email (queued, not sent): to=%s subject=%s",
                to,
                subject,
            )
            return False
        # TODO: integrate real email provider here
        logger.info("Email sent: to=%s subject=%s", to, subject)
        return True

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


# Singleton for easy import
email_service = EmailNotificationService()
