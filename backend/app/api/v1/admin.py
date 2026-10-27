from typing import Optional, List, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.api.deps import get_db, require_admin, require_moderator_or_admin
from app.models.user import User
from app.models.report import CommunityReport
from app.models.evidence import EvidenceSource
from app.models.audit import AuditLog
from app.models.settings import SystemSetting
from app.schemas.report import ReportResponse, ReportListResponse, ReportModerationUpdate
from app.schemas.admin import (
    AdminUserResponse, AdminUserListResponse, UserRoleUpdate,
    AuditLogResponse, AuditLogListResponse,
    SystemSettingResponse, SystemSettingUpdate
)
from app.schemas.evidence import EvidenceSourceResponse, EvidenceSourceListResponse
from app.services.moderation_service import transition_report_status
from app.services.audit_service import record_audit_log

router = APIRouter(prefix="/admin", tags=["Administration & Operations"])


def _format_report(report: CommunityReport) -> ReportResponse:
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
        reporterName=report.reporter_name,
        provenance=report.provenance,
        corroborations=report.corroborations,
        moderatorNotes=report.moderator_notes,
        createdAt=report.created_at,
        updatedAt=report.updated_at
    )


# -----------------------------------------------------------------------------
# REPORT MODERATION
# -----------------------------------------------------------------------------
@router.get("/reports", response_model=ReportListResponse)
def list_admin_reports(
    status: Optional[str] = Query(None, description="Filter by status: pending, approved, rejected, flagged"),
    query: Optional[str] = Query(None, description="Search term for location or description"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_moderator_or_admin),
    db: Session = Depends(get_db)
) -> Any:
    """List reports for moderator review with pagination and filtering."""
    q = db.query(CommunityReport)
    if status and status != "all":
        q = q.filter(CommunityReport.status == status)
    if query:
        search = f"%{query.strip().lower()}%"
        q = q.filter(
            CommunityReport.location.ilike(search) | CommunityReport.description.ilike(search)
        )

    total = q.count()
    items = q.order_by(desc(CommunityReport.created_at)).offset((page - 1) * pageSize).limit(pageSize).all()

    return ReportListResponse(
        items=[_format_report(r) for r in items],
        page=page,
        pageSize=pageSize,
        total=total
    )


@router.patch("/reports/{report_id}", response_model=ReportResponse)
def moderate_report(
    report_id: str,
    payload: ReportModerationUpdate,
    current_user: User = Depends(require_moderator_or_admin),
    db: Session = Depends(get_db)
) -> Any:
    """Review and transition the status of a community report (pending, approved, rejected, flagged)."""
    report = db.query(CommunityReport).filter(CommunityReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")

    updated_report = transition_report_status(
        db=db,
        report=report,
        new_status=payload.status,
        reason=payload.reason,
        reviewer=current_user
    )
    return _format_report(updated_report)


from app.core.encryption import mask_email
from app.schemas.admin import AdminIdentityRevealRequest, AdminUserIdentityResponse
from datetime import datetime, timezone



# -----------------------------------------------------------------------------
# USER MANAGEMENT & ROLES (PRIVACY HARDENED)
# -----------------------------------------------------------------------------
@router.get("/users", response_model=AdminUserListResponse)
def list_admin_users(
    query: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
) -> Any:
    """
    List system users with minimum necessary data (Administrator only).
    Personal names, plaintext emails, and sensitive identifiers are masked by default.
    """
    q = db.query(User)
    if query:
        search = f"%{query.strip().lower()}%"
        q = q.filter(User.role.ilike(search) | User.status.ilike(search) | User.id.ilike(search))

    total = q.count()
    users = q.order_by(desc(User.created_at)).offset((page - 1) * pageSize).limit(pageSize).all()

    items = [
        AdminUserResponse(
            id=u.id,
            displayName=f"User-{u.id[:8]}",
            emailMasked=mask_email(u.email),
            role=u.role,
            status=u.status,
            joinedAt=u.created_at,
            reportsCount=len(u.reports),
            savedPlansCount=len(u.saved_journeys)
        )
        for u in users
    ]

    return AdminUserListResponse(items=items, page=page, pageSize=pageSize, total=total)


@router.post("/users/{user_id}/reveal-identity", response_model=AdminUserIdentityResponse)
def reveal_user_identity(
    user_id: str,
    payload: AdminIdentityRevealRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
) -> Any:
    """
    Authorized account support action to reveal sensitive identity details (name and email).
    Strictly restricted to administrators and logged to the immutable audit trail.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    now = datetime.now(timezone.utc)
    record_audit_log(
        db=db,
        action="Sensitive Identity Revealed",
        record=f"Identity accessed for user {user.id} ({mask_email(user.email)}). Justification: {payload.reason}",
        actor=current_user.name,
        actor_id=current_user.id,
        actor_role=current_user.role
    )

    return AdminUserIdentityResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        status=user.status,
        joinedAt=user.created_at,
        revealedAt=now,
        revealedBy=current_user.name,
        justification=payload.reason
    )


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
def update_user_role(
    user_id: str,
    payload: UserRoleUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
) -> Any:
    """Update user role (traveller, moderator, administrator) with server authorization."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    old_role = user.role
    user.role = payload.role
    db.commit()
    db.refresh(user)

    record_audit_log(
        db=db,
        action="User Role Updated",
        record=f"User {user.id}: {old_role} -> {user.role}",
        actor=current_user.name,
        actor_id=current_user.id,
        actor_role=current_user.role
    )

    return AdminUserResponse(
        id=user.id,
        displayName=f"User-{user.id[:8]}",
        emailMasked=mask_email(user.email),
        role=user.role,
        status=user.status,
        joinedAt=user.created_at,
        reportsCount=len(user.reports),
        savedPlansCount=len(user.saved_journeys)
    )



# -----------------------------------------------------------------------------
# DATA SOURCES HEALTH
# -----------------------------------------------------------------------------
@router.get("/data-sources", response_model=EvidenceSourceListResponse)
def list_data_sources(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
) -> Any:
    """Inspect data sources, ingestion frequencies, and staleness warnings."""
    sources = db.query(EvidenceSource).all()
    items = [
        EvidenceSourceResponse(
            id=s.id,
            name=s.name,
            type=s.type,
            coverage=s.coverage,
            refreshFrequency=s.refresh_frequency,
            lastIngested=s.last_ingested,
            recordsCount=s.records_count,
            status=s.status,
            staleWarning=s.stale_warning,
            notes=s.notes
        )
        for s in sources
    ]
    return EvidenceSourceListResponse(items=items, total=len(items))


# -----------------------------------------------------------------------------
# AUDIT TRAIL
# -----------------------------------------------------------------------------
@router.get("/audit", response_model=AuditLogListResponse)
def list_audit_logs(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
) -> Any:
    """Retrieve immutable administrative and security audit trail."""
    logs = db.query(AuditLog).order_by(desc(AuditLog.timestamp)).limit(200).all()
    items = [
        AuditLogResponse(
            id=l.id,
            timestamp=l.timestamp,
            action=l.action,
            record=l.record,
            actor=l.actor,
            actorRole=l.actor_role,
            outcome=l.outcome,
            environment=l.environment
        )
        for l in logs
    ]
    return AuditLogListResponse(items=items, total=len(items))


# -----------------------------------------------------------------------------
# SYSTEM SETTINGS
# -----------------------------------------------------------------------------
@router.get("/settings", response_model=SystemSettingResponse)
def get_system_settings(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
) -> Any:
    """Retrieve current data governance and moderation settings."""
    setting = db.query(SystemSetting).first()
    if not setting:
        setting = SystemSetting()
        db.add(setting)
        db.commit()
        db.refresh(setting)

    return SystemSettingResponse(
        freshnessThresholdDays=setting.freshness_threshold_days,
        outdatedThresholdDays=setting.outdated_threshold_days,
        autoFlagKeywords=setting.auto_flag_keywords,
        requireModeratorApproval=setting.require_moderator_approval,
        evidenceWeightLighting=setting.evidence_weight_lighting,
        evidenceWeightActivity=setting.evidence_weight_activity,
        timeWeight=setting.time_weight
    )


@router.patch("/settings", response_model=SystemSettingResponse)
def update_system_settings(
    payload: SystemSettingUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
) -> Any:
    """Update governance thresholds, keyword triggers, and ranking weights."""
    setting = db.query(SystemSetting).first()
    if not setting:
        setting = SystemSetting()
        db.add(setting)

    update_data = payload.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        # map camelCase to snake_case
        snake_field = {
            "freshnessThresholdDays": "freshness_threshold_days",
            "outdatedThresholdDays": "outdated_threshold_days",
            "autoFlagKeywords": "auto_flag_keywords",
            "requireModeratorApproval": "require_moderator_approval",
            "evidenceWeightLighting": "evidence_weight_lighting",
            "evidenceWeightActivity": "evidence_weight_activity",
            "timeWeight": "time_weight"
        }.get(field, field)
        setattr(setting, snake_field, val)

    db.commit()
    db.refresh(setting)

    record_audit_log(
        db=db,
        action="System Settings Updated",
        record=str(update_data),
        actor=current_user.name,
        actor_id=current_user.id,
        actor_role=current_user.role
    )

    return SystemSettingResponse(
        freshnessThresholdDays=setting.freshness_threshold_days,
        outdatedThresholdDays=setting.outdated_threshold_days,
        autoFlagKeywords=setting.auto_flag_keywords,
        requireModeratorApproval=setting.require_moderator_approval,
        evidenceWeightLighting=setting.evidence_weight_lighting,
        evidenceWeightActivity=setting.evidence_weight_activity,
        timeWeight=setting.time_weight
    )
