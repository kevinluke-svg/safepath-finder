from typing import Optional, List, Any
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.api.deps import get_db, get_current_user, get_optional_current_user
from app.models.report import CommunityReport
from app.models.user import User
from app.models.settings import SystemSetting
from app.schemas.report import ReportCreate, ReportResponse, ReportListResponse
from app.services.moderation_service import evaluate_auto_flag
from app.services.audit_service import record_audit_log

router = APIRouter(prefix="", tags=["Community Observations & Reports"])

CATEGORY_LABELS = {
    "broken_lighting": "Broken street lighting",
    "blocked_footpath": "Blocked footpath",
    "poor_visibility": "Poor visibility / blind curve",
    "construction_hazard": "Construction or pavement hazard",
    "access_facility": "Access or public transit facility",
    "other_concern": "Other street condition"
}


def _format_report_response(report: CommunityReport) -> ReportResponse:
    return ReportResponse(
        id=report.id,
        category=report.category,
        categoryLabel=report.category_label,
        location=report.location,
        description=report.description,
        status=report.status,
        latitude=report.latitude,
        longitude=report.longitude,
        isAnonymous=report.is_anonymous,
        reporterName="Anonymous" if report.is_anonymous else report.reporter_name,
        provenance=report.provenance,
        corroborations=report.corroborations,
        moderatorNotes=report.moderator_notes,
        createdAt=report.created_at,
        updatedAt=report.updated_at
    )


@router.post("/reports", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
def submit_report(
    payload: ReportCreate,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """Submit a localized environmental observation or street hazard report."""
    # Check automated flagging keywords
    settings = db.query(SystemSetting).first()
    keywords = settings.auto_flag_keywords if settings else "harassment, assault, dark, broken, hazard"
    should_autoflag = evaluate_auto_flag(f"{payload.location} {payload.description}", keywords)

    initial_status = "flagged" if should_autoflag else "pending"
    category_label = CATEGORY_LABELS.get(payload.category, "Other street condition")

    is_anon = payload.anonymous or (current_user is None)
    reporter_name = "Anonymous" if is_anon else current_user.name
    provenance = "Anonymous web submission" if is_anon else f"Reported by {current_user.name} ({current_user.role})"

    report = CommunityReport(
        category=payload.category,
        category_label=category_label,
        location=payload.location.strip(),
        description=payload.description.strip(),
        status=initial_status,
        latitude=payload.latitude,
        longitude=payload.longitude,
        is_anonymous=is_anon,
        reporter_id=current_user.id if current_user and not is_anon else None,
        reporter_name=reporter_name,
        provenance=provenance,
        corroborations=1,
        moderator_notes="Automatically flagged for review based on hazard keyword match." if should_autoflag else ""
    )

    db.add(report)
    db.commit()
    db.refresh(report)

    record_audit_log(
        db=db,
        action="Report Submitted",
        record=f"{report.id}: {report.category} at '{report.location}' (status: {initial_status})",
        actor=reporter_name,
        actor_id=current_user.id if current_user else None,
        actor_role=current_user.role if current_user else "Anonymous"
    )

    return _format_report_response(report)


@router.get("/reports", response_model=ReportListResponse)
def get_public_reports(
    category: Optional[str] = Query(None, description="Filter by report category"),
    status: Optional[str] = Query(None, description="Filter by moderation status"),
    query: Optional[str] = Query(None, description="Text search across location and description"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
) -> Any:
    """List community reports with category, status, and keyword filters."""
    q = db.query(CommunityReport)

    if category and category != "all":
        q = q.filter(CommunityReport.category == category)
    if status and status != "all":
        q = q.filter(CommunityReport.status == status)
    else:
        # Default public listing excludes rejected reports
        q = q.filter(CommunityReport.status != "rejected")

    if query:
        search = f"%{query.strip().lower()}%"
        q = q.filter(
            CommunityReport.location.ilike(search) | CommunityReport.description.ilike(search)
        )

    total = q.count()
    items = q.order_by(desc(CommunityReport.created_at)).offset((page - 1) * pageSize).limit(pageSize).all()

    return ReportListResponse(
        items=[_format_report_response(r) for r in items],
        page=page,
        pageSize=pageSize,
        total=total
    )


@router.get("/reports/mine", response_model=List[ReportResponse])
def get_my_reports(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """Retrieve all reports submitted by the authenticated traveller."""
    reports = db.query(CommunityReport).filter(
        CommunityReport.reporter_id == current_user.id
    ).order_by(desc(CommunityReport.created_at)).all()

    return [_format_report_response(r) for r in reports]
