import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any, List
import logging

from app.core.config import settings
from app.core.encryption import mask_email

logger = logging.getLogger("safepath.email")

# In-memory test mailbox for automated testing verification
TEST_DISPATCHED_EMAILS: List[Dict[str, Any]] = []


def is_mail_configured() -> bool:
    """Check if outbound SMTP server configuration is present in environment."""
    return bool(settings.SMTP_HOST and settings.SMTP_HOST.strip())


def send_password_reset_email(to_email: str, raw_token: str) -> Dict[str, Any]:
    """
    Dispatch a password reset link to a user.
    - If SMTP is configured, sends via smtplib.
    - If not configured, records neutral pending/simulated delivery status.
    - Sensitive token is NEVER logged in application logs.
    """
    reset_url = f"{settings.FRONTEND_BASE_URL}/safepath_pro.html?auth=reset&token={raw_token}"
    masked = mask_email(to_email)
    
    # Record in test mailbox for automated test assertions
    TEST_DISPATCHED_EMAILS.append({
        "type": "password_reset",
        "to_email": to_email,
        "raw_token": raw_token,
        "reset_url": reset_url
    })

    if not is_mail_configured():
        logger.info(f"Password reset link generated for {masked}. [Status: simulated_delivery_no_smtp_configured]")
        return {
            "delivery_status": "simulated_development",
            "provider": "None configured (Set SMTP_HOST in .env for production email dispatch)",
            "recipient_masked": masked
        }

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "SafePath Finder — Password Reset Request"
        msg["From"] = settings.SMTP_FROM
        msg["To"] = to_email

        text = (
            f"Hello,\n\n"
            f"A password reset was requested for your SafePath Finder account.\n\n"
            f"Click the link below to set a new password:\n{reset_url}\n\n"
            f"This link expires in 30 minutes and can only be used once.\n"
            f"If you did not request this, please ignore this email."
        )
        msg.attach(MIMEText(text, "plain"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            if settings.SMTP_TLS:
                server.starttls()
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM, [to_email], msg.as_string())

        logger.info(f"Password reset email dispatched to {masked}")
        return {
            "delivery_status": "dispatched",
            "provider": settings.SMTP_HOST,
            "recipient_masked": masked
        }
    except Exception as e:
        logger.error(f"Failed to dispatch password reset email to {masked}: {str(e)}")
        return {
            "delivery_status": "failed",
            "error": str(e),
            "recipient_masked": masked
        }


def send_feedback_notification_email(feedback_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Notify administrative support staff when new user feedback is submitted.
    Does not crash or fail feedback persistence if notification delivery fails.
    """
    category = feedback_data.get("category", "General")
    fb_id = feedback_data.get("id", "Unknown")

    if not is_mail_configured():
        return {
            "delivery_status": "not_configured",
            "provider": "None"
        }

    admin_to = getattr(settings, "SUPPORT_EMAIL", None) or settings.SMTP_FROM
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[SafePath Feedback] New submission: {category} ({fb_id})"
        msg["From"] = settings.SMTP_FROM
        msg["To"] = admin_to

        text = (
            f"New feedback received in SafePath Finder:\n\n"
            f"ID: {fb_id}\n"
            f"Category: {category}\n"
            f"Rating: {feedback_data.get('rating', 'N/A')}\n"
            f"Message: {feedback_data.get('message')}\n"
        )
        msg.attach(MIMEText(text, "plain"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            if settings.SMTP_TLS:
                server.starttls()
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM, [admin_to], msg.as_string())

        return {"delivery_status": "dispatched"}
    except Exception as e:
        logger.warning(f"Feedback email notification failed: {str(e)}")
        return {"delivery_status": "failed", "error": str(e)}
