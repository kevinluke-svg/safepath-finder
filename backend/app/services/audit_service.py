from typing import Optional, Any
from sqlalchemy.orm import Session
from app.models.audit import AuditLog
from app.core.config import settings


def record_audit_log(
    db: Session,
    action: str,
    record: Any,
    actor: str,
    actor_id: Optional[str] = None,
    actor_role: str = "System",
    outcome: str = "Success"
) -> AuditLog:
    """Persist an audit record for administrative or security-relevant operations."""
    record_text = record if isinstance(record, str) else str(record)
    entry = AuditLog(
        action=action,
        record=record_text,
        actor=actor,
        actor_id=actor_id,
        actor_role=actor_role,
        outcome=outcome,
        environment=f"{settings.ENVIRONMENT.capitalize()} API"
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
