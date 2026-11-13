import math
from typing import Optional, List, Any, Dict
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.api.deps import get_db, get_current_user, get_optional_current_user
from app.models.report import CommunityReport, ReportCorroboration
from app.models.user import User
from app.models.settings import SystemSetting
from app.schemas.report import (
    ReportCreate,
    ReportUpdate,
    ReportResponse,
    ReportListResponse,
    CorroborationResponse,
    ReportFeedbackResponse,
)
from app.services.moderation_service import evaluate_auto_flag
from app.services.audit_service import record_audit_log

router = APIRouter(prefix="", tags=["Community Observations & Reports"])

CATEGORY_LABELS = {
    "broken_lighting": "Broken street lighting",
    "blocked_footpath": "Blocked footpath",
    "poor_visibility": "Poor visibility / blind curve",
    "construction_hazard": "Construction or pavement hazard",
    "access_facility": "Access or public transit facility",
    "crossing_issue": "Pedestrian crossing issue",
    "infrastructure_deficiency": "Footpath or accessibility deficiency",
    "crime_incident": "Crime or safety incident",
    "other_concern": "Other street condition",
    # Street Dog encounter categories (Priority 2)
    "dog_sighting": "Dog sighting (calm / informational)",
    "dog_group": "Group or pack of dogs",
    "dog_aggressive": "Aggressive dog encounter (chasing / threatening)",
    "dog_bite": "Dog bite or physical attack"
}


def _haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes great-circle distance between two points in meters."""
    r = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


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
        locationConfidence=getattr(report, "location_confidence", "user_pinned"),
        duplicateOfId=getattr(report, "duplicate_of_id", None),
        isAnonymous=report.is_anonymous,
        reporterName="Anonymous" if report.is_anonymous else report.reporter_name,
        provenance=report.provenance,
        corroborations=report.corroborations,
        outdatedFlags=getattr(report, "outdated_flags", 0),
        moderatorNotes=report.moderator_notes,
        encounterTime=report.encounter_time,
        dogCount=report.dog_count,
        isAggressive=report.is_aggressive,
        createdAt=report.created_at,
        updatedAt=report.updated_at
    )


@router.post("/reports", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
def submit_report(
    payload: ReportCreate,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """Submit a localized environmental observation, street hazard, or dog encounter report."""
    now = datetime.now(timezone.utc)

    # 1. Rate Limiting Protection (Anti-Abuse)
    ten_mins_ago = now - timedelta(minutes=10)
    if current_user:
        recent_count = db.query(CommunityReport).filter(
            CommunityReport.reporter_id == current_user.id,
            CommunityReport.created_at >= ten_mins_ago
        ).count()
    else:
        recent_count = db.query(CommunityReport).filter(
            CommunityReport.reporter_id.is_(None),
            CommunityReport.created_at >= ten_mins_ago
        ).count()

    if recent_count >= 10:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Submission rate limit exceeded. Please wait a few minutes before submitting another report."
        )

    # 2. Date and time validation
    if payload.encounterTime:
        enc_time = payload.encounterTime if payload.encounterTime.tzinfo else payload.encounterTime.replace(tzinfo=timezone.utc)
        if enc_time > now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Encounter date and time cannot be in the future."
            )

    # 3. Coordinate range validation
    if payload.latitude is not None and not (-90.0 <= payload.latitude <= 90.0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Latitude {payload.latitude} is invalid; must be between -90.0 and 90.0."
        )
    if payload.longitude is not None and not (-180.0 <= payload.longitude <= 180.0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Longitude {payload.longitude} is invalid; must be between -180.0 and 180.0."
        )

    # 4. Duplicate Detection Support
    duplicate_of_id = None
    if payload.latitude is not None and payload.longitude is not None:
        two_days_ago = now - timedelta(days=2)
        candidates = db.query(CommunityReport).filter(
            CommunityReport.category == payload.category,
            CommunityReport.status != "rejected",
            CommunityReport.created_at >= two_days_ago,
            CommunityReport.latitude.isnot(None),
            CommunityReport.longitude.isnot(None)
        ).all()

        for cand in candidates:
            dist = _haversine_distance_meters(payload.latitude, payload.longitude, cand.latitude, cand.longitude)
            if dist <= 30.0:  # Within 30 meters
                if current_user and cand.reporter_id == current_user.id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Duplicate submission: You have already submitted a report for '{payload.category}' at this location within the last 48 hours (Report ID: {cand.id})."
                    )
                else:
                    duplicate_of_id = cand.id
                    cand.corroborations += 1
                    cand.updated_at = now
                    if current_user:
                        existing_corr = db.query(ReportCorroboration).filter_by(report_id=cand.id, user_id=current_user.id).first()
                        if not existing_corr:
                            db.add(ReportCorroboration(report_id=cand.id, user_id=current_user.id))
                    break

    # 5. Derive behavioral aggressiveness for dog categories
    is_aggressive = payload.isAggressive
    if payload.category in ("dog_aggressive", "dog_bite") and is_aggressive is None:
        is_aggressive = True
    elif payload.category == "dog_sighting" and is_aggressive is None:
        is_aggressive = False

    # 6. Check automated flagging keywords
    system_settings = db.query(SystemSetting).first()
    keywords = system_settings.auto_flag_keywords if system_settings else "harassment, assault, dark, broken, hazard"
    should_autoflag = evaluate_auto_flag(f"{payload.location} {payload.description}", keywords)
    if payload.category == "dog_bite":
        should_autoflag = True

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
        location_confidence=payload.locationConfidence or "user_pinned",
        duplicate_of_id=duplicate_of_id,
        encounter_time=payload.encounterTime,
        dog_count=payload.dogCount,
        is_aggressive=is_aggressive,
        is_anonymous=is_anon,
        reporter_id=current_user.id if current_user and not is_anon else None,
        reporter_name=reporter_name,
        provenance=provenance,
        corroborations=1,
        moderator_notes="Automatically flagged for priority review based on keyword/severity match." if should_autoflag else ""
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


@router.post("/reports/{report_id}/corroborate", response_model=CorroborationResponse)
def corroborate_report(
    report_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Allow distinct authenticated users to confirm or corroborate a community report.
    Guarantees that a reporter cannot self-corroborate and that a single account cannot
    corroborate repeatedly to artificially inflate evidence.
    """
    report = db.query(CommunityReport).filter(CommunityReport.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found."
        )

    if report.reporter_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot corroborate your own report."
        )

    existing = db.query(ReportCorroboration).filter_by(
        report_id=report.id,
        user_id=current_user.id
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already corroborated this report."
        )

    corroboration = ReportCorroboration(
        report_id=report.id,
        user_id=current_user.id
    )
    db.add(corroboration)
    report.corroborations += 1
    report.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(report)

    record_audit_log(
        db=db,
        action="Report Corroborated",
        record=f"{report.id}: corroborated by {current_user.name} (total corroborations: {report.corroborations})",
        actor=current_user.name,
        actor_id=current_user.id,
        actor_role=current_user.role
    )

    return CorroborationResponse(
        message="Community report corroborated successfully.",
        reportId=report.id,
        corroborationsCount=report.corroborations,
        userHasCorroborated=True
    )


@router.post("/reports/{report_id}/confirm", response_model=ReportFeedbackResponse)
def confirm_report_active(
    report_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """Confirm an existing street hazard is still present (idempotent per user)."""
    report = db.query(CommunityReport).filter(CommunityReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    if report.reporter_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot confirm your own report.")

    existing = db.query(ReportCorroboration).filter_by(
        report_id=report.id,
        user_id=current_user.id
    ).first()
    if existing:
        if existing.action == "confirm_present":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You have already confirmed this report.")
        else:
            existing.action = "confirm_present"
            if getattr(report, "outdated_flags", 0) > 0:
                report.outdated_flags -= 1
            report.corroborations += 1
    else:
        corroboration = ReportCorroboration(
            report_id=report.id,
            user_id=current_user.id,
            action="confirm_present"
        )
        db.add(corroboration)
        report.corroborations += 1

    report.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(report)

    record_audit_log(
        db=db,
        action="Report Confirmed Active",
        record=f"{report.id}: confirmed active by user {current_user.id} (total confirmations: {report.corroborations})",
        actor=current_user.name,
        actor_id=current_user.id,
        actor_role=current_user.role
    )

    return ReportFeedbackResponse(
        message="Observation confirmed as still active and relevant.",
        reportId=report.id,
        action="confirm_present",
        corroborationsCount=report.corroborations,
        outdatedFlagsCount=getattr(report, "outdated_flags", 0),
        userActionRecorded=True
    )


@router.post("/reports/{report_id}/outdated", response_model=ReportFeedbackResponse)
def flag_report_outdated(
    report_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """Flag an existing report as resolved or outdated by an independent user."""
    report = db.query(CommunityReport).filter(CommunityReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")

    existing = db.query(ReportCorroboration).filter_by(
        report_id=report.id,
        user_id=current_user.id
    ).first()
    if existing:
        if existing.action == "flag_outdated":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You have already flagged this report as outdated.")
        else:
            existing.action = "flag_outdated"
            if report.corroborations > 1:
                report.corroborations -= 1
            report.outdated_flags = getattr(report, "outdated_flags", 0) + 1
    else:
        corroboration = ReportCorroboration(
            report_id=report.id,
            user_id=current_user.id,
            action="flag_outdated"
        )
        db.add(corroboration)
        report.outdated_flags = getattr(report, "outdated_flags", 0) + 1

    # Auto-flag for moderation review if 3+ independent users flag as outdated
    if getattr(report, "outdated_flags", 0) >= 3 and report.status == "approved":
        report.status = "flagged"
        report.moderator_notes = (report.moderator_notes or "") + " [Auto-flagged: 3+ independent users flagged as outdated/resolved]"

    report.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(report)

    record_audit_log(
        db=db,
        action="Report Flagged Outdated",
        record=f"{report.id}: flagged outdated by user {current_user.id} (total flags: {report.outdated_flags})",
        actor=current_user.name,
        actor_id=current_user.id,
        actor_role=current_user.role
    )

    return ReportFeedbackResponse(
        message="Report flagged as outdated or resolved. Moderation queue updated.",
        reportId=report.id,
        action="flag_outdated",
        corroborationsCount=report.corroborations,
        outdatedFlagsCount=getattr(report, "outdated_flags", 0),
        userActionRecorded=True
    )


@router.get("/reports/mine", response_model=List[ReportResponse])
def get_my_submitted_reports(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """Retrieve all reports contributed by the authenticated traveller with current moderation state."""
    reports = db.query(CommunityReport).filter(
        CommunityReport.reporter_id == current_user.id
    ).order_by(desc(CommunityReport.created_at)).all()
    return [_format_report_response(r) for r in reports]


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
        if "," in category:
            cats = [c.strip() for c in category.split(",") if c.strip()]
            q = q.filter(CommunityReport.category.in_(cats))
        else:
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


@router.get("/reports/public", response_model=List[Dict[str, Any]])
def get_sanitized_public_reports(
    category: Optional[str] = Query(None, description="Filter by category"),
    db: Session = Depends(get_db)
) -> Any:
    """
    Public map evidence feed: returns ONLY approved reports with ALL reporter PII stripped.
    Excludes user IDs, email addresses, phone numbers, and full reporter names.
    """
    q = db.query(CommunityReport).filter(CommunityReport.status == "approved")
    if category and category != "all":
        if "," in category:
            cats = [c.strip() for c in category.split(",") if c.strip()]
            q = q.filter(CommunityReport.category.in_(cats))
        else:
            q = q.filter(CommunityReport.category == category)

    reports = q.order_by(desc(CommunityReport.created_at)).all()
    sanitized = []
    for r in reports:
        sanitized.append({
            "id": r.id,
            "category": r.category,
            "categoryLabel": r.category_label,
            "location": r.location,
            "description": r.description,
            "latitude": r.latitude,
            "longitude": r.longitude,
            "locationConfidence": getattr(r, "location_confidence", "user_pinned"),
            "duplicateOfId": getattr(r, "duplicate_of_id", None),
            "encounterTime": r.encounter_time.isoformat() if r.encounter_time else None,
            "dogCount": r.dog_count,
            "isAggressive": r.is_aggressive,
            "corroborations": r.corroborations,
            "status": r.status,
            "createdAt": r.created_at.isoformat() if r.created_at else None
        })
    return sanitized


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


@router.put("/reports/{report_id}", response_model=ReportResponse)
def update_report(
    report_id: str,
    payload: ReportUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """Allow travellers to correct or update their own submitted reports."""
    report = db.query(CommunityReport).filter(CommunityReport.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found."
        )

    # Permission check: Ordinary user can only modify their own report
    if report.reporter_id != current_user.id and current_user.role not in ("admin", "moderator"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this report."
        )

    if payload.location is not None:
        report.location = payload.location.strip()
    if payload.description is not None:
        report.description = payload.description.strip()
    if payload.category is not None:
        report.category = payload.category
        report.category_label = CATEGORY_LABELS.get(payload.category, "Other street condition")
    if payload.latitude is not None:
        report.latitude = payload.latitude
    if payload.longitude is not None:
        report.longitude = payload.longitude
    if payload.locationConfidence is not None:
        report.location_confidence = payload.locationConfidence
    if payload.encounterTime is not None:
        report.encounter_time = payload.encounterTime
    if payload.dogCount is not None:
        report.dog_count = payload.dogCount
    if payload.isAggressive is not None:
        report.is_aggressive = payload.isAggressive

    report.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(report)

    record_audit_log(
        db=db,
        action="Report Corrected",
        record=f"{report.id}: corrected by {current_user.name}",
        actor=current_user.name,
        actor_id=current_user.id,
        actor_role=current_user.role
    )

    return _format_report_response(report)


@router.delete("/reports/{report_id}")
def withdraw_report(
    report_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """Allow travellers to withdraw their own submitted reports."""
    report = db.query(CommunityReport).filter(CommunityReport.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found."
        )

    if report.reporter_id != current_user.id and current_user.role not in ("admin", "moderator"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to withdraw this report."
        )

    # Soft withdrawal: mark rejected with withdrawal reason
    report.status = "rejected"
    report.moderator_notes = f"Withdrawn by submitter {current_user.name}."
    report.updated_at = datetime.now(timezone.utc)
    db.commit()

    record_audit_log(
        db=db,
        action="Report Withdrawn",
        record=f"{report.id}: withdrawn by submitter",
        actor=current_user.name,
        actor_id=current_user.id,
        actor_role=current_user.role
    )

    return {
        "message": "Report successfully withdrawn.",
        "id": report.id,
        "status": "rejected",
        "moderatorNotes": report.moderator_notes
    }
