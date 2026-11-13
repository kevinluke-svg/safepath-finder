import secrets
from datetime import datetime, timezone, timedelta
from typing import List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.contact import TrustedContact, JourneyShare, ArrivalConfirmation, JourneySession
from app.core.encryption import encrypt_field, decrypt_field, mask_phone_number
from app.schemas.contact import (
    TrustedContactCreate, TrustedContactUpdate, TrustedContactResponse,
    JourneyShareRequest, JourneyShareResponse,
    ArrivalConfirmationRequest, ArrivalConfirmationResponse,
    JourneySessionStartRequest, JourneySessionResponse, PublicJourneyShareView
)
from app.schemas.auth import GenericResponse
from app.services.audit_service import record_audit_log

router = APIRouter(prefix="", tags=["Trusted Contacts & Journey Sharing"])


@router.get("/trusted-contacts", response_model=List[TrustedContactResponse])

def get_trusted_contacts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    List trusted safety contacts configured by the authenticated traveller.
    Decrypted transparently only for the authorized contact owner.
    """
    contacts = db.query(TrustedContact).filter(
        TrustedContact.user_id == current_user.id
    ).order_by(desc(TrustedContact.created_at)).all()

    return [
        TrustedContactResponse(
            id=c.id,
            name=decrypt_field(c.name),
            relationship=c.relationship,
            phone=decrypt_field(c.phone),
            notifyOnStart=c.notify_on_start,
            notifyOnArrival=c.notify_on_arrival,
            createdAt=c.created_at
        )
        for c in contacts
    ]


@router.post("/trusted-contacts", response_model=TrustedContactResponse, status_code=status.HTTP_201_CREATED)
def add_trusted_contact(
    payload: TrustedContactCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Add a new trusted safety contact.
    Names and phone numbers are encrypted with AES-128 Fernet at rest.
    """
    clean_name = payload.name.strip()
    clean_phone = payload.phone.strip()

    contact = TrustedContact(
        user_id=current_user.id,
        name=encrypt_field(clean_name),
        relationship=payload.relationship.strip(),
        phone=encrypt_field(clean_phone),
        notify_on_start=True,
        notify_on_arrival=True
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)

    record_audit_log(
        db=db,
        action="Added Trusted Contact",
        record=f"Contact {contact.id} added for user {current_user.id} ({mask_phone_number(clean_phone)})",
        actor=current_user.name,
        actor_id=current_user.id,
        actor_role=current_user.role
    )

    return TrustedContactResponse(
        id=contact.id,
        name=clean_name,
        relationship=contact.relationship,
        phone=clean_phone,
        notifyOnStart=contact.notify_on_start,
        notifyOnArrival=contact.notify_on_arrival,
        createdAt=contact.created_at
    )


@router.patch("/trusted-contacts/{contact_id}", response_model=TrustedContactResponse)
def update_trusted_contact(
    contact_id: str,
    payload: TrustedContactUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Update a trusted contact (IDOR protected).
    Enforces user ownership and re-encrypts sensitive fields.
    """
    contact = db.query(TrustedContact).filter(TrustedContact.id == contact_id).first()
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found."
        )
    if contact.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to modify another user's contact."
        )

    if payload.name is not None:
        contact.name = encrypt_field(payload.name.strip())
    if payload.relationship is not None:
        contact.relationship = payload.relationship.strip()
    if payload.phone is not None:
        contact.phone = encrypt_field(payload.phone.strip())
    if payload.notifyOnStart is not None:
        contact.notify_on_start = payload.notifyOnStart
    if payload.notifyOnArrival is not None:
        contact.notify_on_arrival = payload.notifyOnArrival

    db.commit()
    db.refresh(contact)

    record_audit_log(
        db=db,
        action="Updated Trusted Contact",
        record=f"Contact {contact.id} updated for user {current_user.id}",
        actor=current_user.name,
        actor_id=current_user.id,
        actor_role=current_user.role
    )

    return TrustedContactResponse(
        id=contact.id,
        name=decrypt_field(contact.name),
        relationship=contact.relationship,
        phone=decrypt_field(contact.phone),
        notifyOnStart=contact.notify_on_start,
        notifyOnArrival=contact.notify_on_arrival,
        createdAt=contact.created_at
    )


@router.delete("/trusted-contacts/{contact_id}", response_model=GenericResponse)
def delete_trusted_contact(
    contact_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """Delete a trusted contact (IDOR protected)."""
    contact = db.query(TrustedContact).filter(TrustedContact.id == contact_id).first()
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found."
        )
    if contact.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to delete another user's contact."
        )

    db.delete(contact)
    db.commit()


    record_audit_log(
        db=db,
        action="Removed Trusted Contact",
        record=f"Contact {contact_id} removed by user {current_user.id}",
        actor=current_user.name,
        actor_id=current_user.id,
        actor_role=current_user.role
    )

    return GenericResponse(status=200, message="Trusted contact removed.", success=True)



@router.post("/journey-shares", response_model=JourneyShareResponse)
def share_journey(
    payload: JourneyShareRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Generate a live trip share link and dispatch notification preview.
    Complies with API contract: does NOT infer delivery; returns pending_provider_integration.
    """
    preview = f"SafePath Walk: I am walking to {payload.destination} via {payload.routeName}. Estimated walk duration: {payload.etaMinutes} mins."
    share_record = JourneyShare(
        user_id=current_user.id,
        route_name=payload.routeName,
        destination=payload.destination,
        eta_minutes=payload.etaMinutes,
        contact_count=len(payload.contactIds),
        delivery_status="pending_provider_integration",
        provider_name="None configured (Backend integration required)",
        preview_message=preview
    )
    db.add(share_record)
    db.commit()

    record_audit_log(
        db=db,
        action="Journey Share Initiated",
        record=f"Dest: {payload.destination}, Contacts: {len(payload.contactIds)}",
        actor=current_user.name,
        actor_id=current_user.id,
        actor_role=current_user.role
    )

    return JourneyShareResponse(
        deliveryStatus="pending_provider_integration",
        providerName="None configured (Backend integration required)",
        deliveredCount=0,
        intendedCount=len(payload.contactIds),
        shareLink=f"http://localhost:8000/safepath_pro.html?preview_journey=true&dest={payload.destination}",
        previewMessage=preview
    )


@router.post("/arrival-confirmations", response_model=ArrivalConfirmationResponse)
def confirm_arrival(
    payload: ArrivalConfirmationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Record an arrival confirmation at destination.
    Complies with API contract: explicitly informs that automatic SMS/WhatsApp alerts require gateway integration.
    """
    arrival = ArrivalConfirmation(
        user_id=current_user.id,
        destination=payload.destination,
        journey_id=payload.journeyId,
        arrival_confirmed=True,
        delivery_status="pending_provider_integration",
        message="Arrival recorded on server. Automatic SMS/WhatsApp alerts require SMS gateway integration."
    )
    db.add(arrival)
    db.commit()

    record_audit_log(
        db=db,
        action="Arrival Confirmed",
        record=f"Destination: {payload.destination}",
        actor=current_user.name,
        actor_id=current_user.id,
        actor_role=current_user.role
    )

    return ArrivalConfirmationResponse(
        arrivalConfirmed=True,
        timestamp=arrival.timestamp,
        deliveryStatus="pending_provider_integration",
        message="Arrival recorded on server. Automatic SMS/WhatsApp alerts require SMS gateway integration."
    )


# -----------------------------------------------------------------------------
# Phase 3: Active Journey Sharing Sessions & Public Viewing
# -----------------------------------------------------------------------------
def _format_journey_session_response(sess: JourneySession) -> JourneySessionResponse:
    return JourneySessionResponse(
        id=sess.id,
        token=sess.token,
        origin=sess.origin,
        destination=sess.destination,
        routeName=sess.route_name,
        routeId=sess.route_id,
        etaMinutes=sess.eta_minutes,
        distanceMeters=sess.distance_meters,
        status=sess.status,
        consentGiven=sess.consent_given,
        startedAt=sess.started_at,
        expectedArrivalAt=sess.expected_arrival_at,
        completedAt=sess.completed_at,
        expiresAt=sess.expires_at,
        isRevoked=sess.is_revoked,
        contactCount=sess.contact_count,
        shareUrl=f"/safepath_pro.html?share_token={sess.token}",
        reminderMinutesBefore=5,
        notificationMode=sess.notification_mode
    )


@router.post("/journey-sessions/start", response_model=JourneySessionResponse, status_code=status.HTTP_201_CREATED)
def start_journey_session(
    payload: JourneySessionStartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Start an active journey sharing session with voluntary consent.
    Generates a cryptographically secure token for designated trusted contacts.
    """
    if not payload.consentGiven:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Voluntary consent is required to share your journey itinerary and ETA."
        )

    now = datetime.now(timezone.utc)
    expected_arrival = now + timedelta(minutes=payload.etaMinutes)
    expires = expected_arrival + timedelta(hours=2)
    token = secrets.token_urlsafe(24)

    session = JourneySession(
        user_id=current_user.id,
        token=token,
        origin=payload.origin.strip(),
        destination=payload.destination.strip(),
        route_name=payload.routeName.strip(),
        route_id=payload.routeId.strip(),
        eta_minutes=payload.etaMinutes,
        distance_meters=payload.distanceMeters or 0,
        status="active",
        consent_given=True,
        contact_count=max(len(payload.contactIds), 1),
        contact_ids=",".join(payload.contactIds) if payload.contactIds else "",
        started_at=now,
        expected_arrival_at=expected_arrival,
        expires_at=expires,
        is_revoked=False,
        reminder_sent=False,
        overdue_notified=False,
        notification_mode="simulated_development"
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    record_audit_log(
        db=db,
        action="Journey Session Started",
        record=f"Session {session.id} for user {current_user.id} -> {session.destination} (ETA: {session.eta_minutes}m)",
        actor=current_user.name,
        actor_id=current_user.id,
        actor_role=current_user.role
    )

    return _format_journey_session_response(session)


@router.post("/journey-sessions/{session_id}/check-in", response_model=JourneySessionResponse)
def check_in_journey_arrival(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """Check in safely upon reaching destination. Completes the active session."""
    session = db.query(JourneySession).filter(JourneySession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journey session not found.")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to check in for this session.")
    if session.status == "completed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Journey session is already completed.")

    now = datetime.now(timezone.utc)
    session.status = "completed"
    session.completed_at = now
    db.commit()
    db.refresh(session)

    record_audit_log(
        db=db,
        action="Journey Safe Check-in",
        record=f"Session {session.id} completed safely by {current_user.name}",
        actor=current_user.name,
        actor_id=current_user.id,
        actor_role=current_user.role
    )

    return _format_journey_session_response(session)


@router.post("/journey-sessions/{session_id}/cancel", response_model=JourneySessionResponse)
def cancel_journey_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """Revoke or end active journey sharing."""
    session = db.query(JourneySession).filter(JourneySession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journey session not found.")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to cancel this session.")

    now = datetime.now(timezone.utc)
    session.status = "cancelled"
    session.is_revoked = True
    session.revoked_at = now
    db.commit()
    db.refresh(session)

    record_audit_log(
        db=db,
        action="Journey Session Cancelled",
        record=f"Session {session.id} cancelled/revoked by {current_user.name}",
        actor=current_user.name,
        actor_id=current_user.id,
        actor_role=current_user.role
    )

    return _format_journey_session_response(session)


@router.get("/journey-sessions/active", response_model=List[JourneySessionResponse])
def get_active_journey_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """List active, unexpired journey sharing sessions for the authenticated user."""
    now = datetime.now(timezone.utc)
    sessions = db.query(JourneySession).filter(
        JourneySession.user_id == current_user.id,
        JourneySession.status == "active",
        JourneySession.is_revoked == False,
        JourneySession.expires_at >= now
    ).order_by(desc(JourneySession.started_at)).all()

    return [_format_journey_session_response(s) for s in sessions]


@router.get("/journey-shares/public/{token}", response_model=PublicJourneyShareView)
def get_public_journey_share_view(
    token: str,
    db: Session = Depends(get_db)
) -> Any:
    """
    Public tokenized view for trusted contacts.
    Exposes itinerary, ETA, and arrival status WITHOUT leaking user identity, email, or contacts.
    """
    session = db.query(JourneySession).filter(JourneySession.token == token).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shared journey not found or token has expired.")

    now = datetime.now(timezone.utc)
    exp_at = session.expected_arrival_at
    if exp_at and exp_at.tzinfo is None:
        exp_at = exp_at.replace(tzinfo=timezone.utc)

    if session.is_revoked or session.status == "cancelled":
        current_status = "cancelled"
        is_overdue = False
    elif session.status == "completed":
        current_status = "completed"
        is_overdue = False
    elif exp_at and now > exp_at:
        current_status = "overdue"
        is_overdue = True
    else:
        current_status = "active"
        is_overdue = False

    return PublicJourneyShareView(
        token=session.token,
        origin=session.origin,
        destination=session.destination,
        routeName=session.route_name,
        etaMinutes=session.eta_minutes,
        distanceMeters=session.distance_meters,
        status=current_status,
        startedAt=session.started_at,
        expectedArrivalAt=session.expected_arrival_at,
        completedAt=session.completed_at,
        isOverdue=is_overdue
    )


@router.post("/journey-sessions/{session_id}/simulate-reminder", response_model=GenericResponse)
def simulate_journey_reminder(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """Simulate arrival countdown reminder (for development and demonstration)."""
    session = db.query(JourneySession).filter(JourneySession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized access.")

    session.reminder_sent = True
    db.commit()

    return GenericResponse(
        status=200,
        message=f"[SIMULATED ALERT] Reminder sent for journey to {session.destination}. Expected arrival at {session.expected_arrival_at.strftime('%H:%M UTC')}.",
        success=True
    )

