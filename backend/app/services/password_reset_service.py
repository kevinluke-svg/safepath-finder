import secrets
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.user import User
from app.models.password_reset import PasswordResetToken
from app.core.security import get_password_hash
from app.services.audit_service import record_audit_log
from app.services import email_service


def hash_token(token: str) -> str:
    """Compute SHA-256 digest of a raw token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def request_password_reset(db: Session, email: str) -> bool:
    """
    Handle password recovery request.
    Always returns True (for a neutral 202 response) to prevent account enumeration.
    Enforces rate-limiting: max 3 requests in the last 15 minutes.
    """
    clean_email = email.strip().lower()
    user = db.query(User).filter(User.email == clean_email).first()
    
    if not user or user.status == "suspended":
        # Neutral response without revealing nonexistence or suspension
        return True

    now = datetime.now(timezone.utc)
    fifteen_mins_ago = now - timedelta(minutes=15)

    # Rate limiting: count recent tokens created for this user
    recent_tokens_count = db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.created_at >= fifteen_mins_ago
    ).count()

    if recent_tokens_count >= 3:
        # Rate limit exceeded: log internally but keep response neutral
        record_audit_log(
            db=db,
            action="Password Reset Rate Limited",
            record=f"Rate limit exceeded (3 reqs in 15m) for user {user.id}",
            actor="System",
            actor_role="System"
        )
        return True

    # Generate cryptographically secure token
    raw_token = secrets.token_urlsafe(32)
    token_digest = hash_token(raw_token)
    expires_at = now + timedelta(minutes=30)

    reset_record = PasswordResetToken(
        user_id=user.id,
        token_hash=token_digest,
        expires_at=expires_at,
        used=False
    )
    db.add(reset_record)
    db.commit()

    # Dispatch email (raw_token is NEVER logged or returned to client)
    email_service.send_password_reset_email(user.email, raw_token)

    record_audit_log(
        db=db,
        action="Password Reset Requested",
        record=f"Token generated (expires {expires_at.isoformat()}) for user {user.id}",
        actor="System",
        actor_role="System"
    )

    return True


def confirm_password_reset(db: Session, raw_token: str, new_password: str) -> User:
    """
    Verify single-use token and update user password with Argon2id.
    Invalidates the token upon use and burns any remaining tokens for this user.
    """
    if not raw_token or len(raw_token) < 16:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or malformed password reset token."
        )

    if len(new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 8 characters long."
        )

    token_digest = hash_token(raw_token)
    now = datetime.now(timezone.utc)

    token_record = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == token_digest,
        PasswordResetToken.used == False
    ).first()

    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or already used password reset token."
        )

    # Check expiration
    # Ensure timezone awareness for comparison
    token_expiry = token_record.expires_at
    if token_expiry.tzinfo is None:
        token_expiry = token_expiry.replace(tzinfo=timezone.utc)

    if token_expiry < now:
        token_record.used = True
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password reset token has expired. Please request a new link."
        )

    user = db.query(User).filter(User.id == token_record.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account associated with this token could not be found."
        )

    # Invalidate token (single-use)
    token_record.used = True

    # Invalidate any other active reset tokens for this user
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used == False
    ).update({"used": True})

    # Update password using Argon2id
    user.hashed_password = get_password_hash(new_password)
    db.commit()

    record_audit_log(
        db=db,
        action="Password Reset Completed",
        record=f"Password reset completed with Argon2id hash for user {user.id}",
        actor="System",
        actor_role="System"
    )

    return user
