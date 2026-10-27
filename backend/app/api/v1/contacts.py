from datetime import datetime, timezone
from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.contact import TrustedContact, JourneyShare, ArrivalConfirmation
from app.core.encryption import encrypt_field, decrypt_field, mask_phone_number
from app.schemas.contact import (
    TrustedContactCreate, TrustedContactUpdate, TrustedContactResponse,
    JourneyShareRequest, JourneyShareResponse,
    ArrivalConfirmationRequest, ArrivalConfirmationResponse
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
