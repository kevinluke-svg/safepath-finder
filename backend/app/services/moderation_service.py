from datetime import datetime, timezone
from typing import Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.report import CommunityReport
from app.models.user import User
from app.services.audit_service import record_audit_log

ALLOWED_TRANSITIONS = {
    "pending": {"approved", "rejected", "flagged"},
    "approved": {"flagged", "rejected", "pending"},
    "flagged": {"approved", "rejected", "pending"},
    "rejected": {"pending", "flagged"}
}


def evaluate_auto_flag(text: str, keywords_csv: str) -> bool:
    """Return True if text contains any configured autoflag keywords."""
    if not text or not keywords_csv:
        return False
    lower_text = text.lower()
    keywords = [k.strip().lower() for k in keywords_csv.split(",") if k.strip()]
    return any(k in lower_text for k in keywords)


def transition_report_status(
    db: Session,
    report: CommunityReport,
    new_status: str,
    reason: str,
    reviewer: User
) -> CommunityReport:
    """Validate and execute a moderation state transition on a community report."""
    current_status = report.status
    if new_status == current_status:
        report.moderator_notes = reason
        db.commit()
        db.refresh(report)
        return report

    allowed = ALLOWED_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status transition from '{current_status}' to '{new_status}'. Allowed target statuses: {', '.join(allowed)}."
        )

    report.status = new_status
    report.moderator_notes = reason.strip()
    report.reviewed_by_id = reviewer.id
    report.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(report)

    # Record administrative action in audit trail
    record_audit_log(
        db=db,
        action=f"Report Moderation: {current_status} -> {new_status}",
        record=f"Report #{report.id} ({report.location}): {reason}",
        actor=reviewer.name,
        actor_id=reviewer.id,
        actor_role=reviewer.role,
        outcome="Success"
    )

    return report
