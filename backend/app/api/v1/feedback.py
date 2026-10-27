from datetime import datetime, timezone
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.api.deps import get_db, get_optional_current_user, require_moderator_or_admin
from app.models.user import User
from app.models.feedback import Feedback
from app.schemas.feedback import (
    FeedbackCreate, FeedbackResponse,
    AdminFeedbackResponse, AdminFeedbackListResponse, AdminFeedbackUpdate
)
from app.services.audit_service import record_audit_log
from app.services import email_service

router = APIRouter(tags=["User Feedback & Support"])


@router.post("/feedback", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
def submit_feedback(
    payload: FeedbackCreate,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Submit user feedback or issue report.
    Supports authenticated or anonymous submission with data minimization.
    Saves feedback record regardless of whether outbound notification email succeeds.
    """
    feedback = Feedback(
        user_id=current_user.id if current_user else None,
        category=payload.category,
        message=payload.message.strip(),
        rating=payload.rating,
        status="new"
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    # Optional email notification to staff (does not fail submission on email error)
    email_service.send_feedback_notification_email({
        "id": feedback.id,
        "category": feedback.category,
        "message": feedback.message,
        "rating": feedback.rating
    })

    record_audit_log(
        db=db,
        action="Feedback Submitted",
        record=f"Feedback {feedback.id} ({feedback.category}) submitted",
        actor=current_user.name if current_user else "Anonymous",
        actor_id=current_user.id if current_user else None,
        actor_role=current_user.role if current_user else "Anonymous"
    )

    return FeedbackResponse(
        id=feedback.id,
        category=feedback.category,
        message=feedback.message,
        rating=feedback.rating,
        status=feedback.status,
        createdAt=feedback.created_at,
        isAnonymous=feedback.user_id is None
    )


@router.get("/admin/feedback", response_model=AdminFeedbackListResponse)
def list_feedback_inbox(
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_moderator_or_admin),
    db: Session = Depends(get_db)
) -> Any:
    """
    Administrative feedback inbox.
    Requires moderator or administrator authorization.
    """
    q = db.query(Feedback)
    if category:
        q = q.filter(Feedback.category == category)
    if status:
        q = q.filter(Feedback.status == status)

    total = q.count()
    items_db = q.order_by(desc(Feedback.created_at)).offset((page - 1) * pageSize).limit(pageSize).all()

    items = [
        AdminFeedbackResponse(
            id=fb.id,
            userId=f"User-{fb.user_id[:8]}" if fb.user_id else None,
            category=fb.category,
            message=fb.message,
            rating=fb.rating,
            status=fb.status,
            createdAt=fb.created_at,
            adminNotes=fb.admin_notes,
            reviewedBy=fb.reviewer.name if fb.reviewer else None,
            reviewedAt=fb.reviewed_at
        )
        for fb in items_db
    ]

    return AdminFeedbackListResponse(
        items=items,
        page=page,
        pageSize=pageSize,
        total=total
    )


@router.patch("/admin/feedback/{feedback_id}", response_model=AdminFeedbackResponse)
def update_feedback_status(
    feedback_id: str,
    payload: AdminFeedbackUpdate,
    current_user: User = Depends(require_moderator_or_admin),
    db: Session = Depends(get_db)
) -> Any:
    """
    Update feedback review status and administrator notes.
    """
    feedback = db.query(Feedback).filter(Feedback.id == feedback_id).first()
    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feedback record not found."
        )

    old_status = feedback.status
    feedback.status = payload.status
    if payload.adminNotes is not None:
        feedback.admin_notes = payload.adminNotes.strip()
    feedback.reviewed_by = current_user.id
    feedback.reviewed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(feedback)

    record_audit_log(
        db=db,
        action="Feedback Status Updated",
        record=f"Feedback {feedback.id}: {old_status} -> {feedback.status}",
        actor=current_user.name,
        actor_id=current_user.id,
        actor_role=current_user.role
    )

    return AdminFeedbackResponse(
        id=feedback.id,
        userId=f"User-{feedback.user_id[:8]}" if feedback.user_id else None,
        category=feedback.category,
        message=feedback.message,
        rating=feedback.rating,
        status=feedback.status,
        createdAt=feedback.created_at,
        adminNotes=feedback.admin_notes,
        reviewedBy=current_user.name,
        reviewedAt=feedback.reviewed_at
    )
