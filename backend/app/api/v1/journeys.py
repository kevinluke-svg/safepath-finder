from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.journey import SavedJourney, JourneyHistory, SavedPlace
from app.schemas.journey import (
    SavedJourneyCreate, SavedJourneyResponse, JourneyHistoryResponse,
    SavedPlaceCreate, SavedPlaceResponse
)
from app.schemas.auth import GenericResponse
from app.services.audit_service import record_audit_log

router = APIRouter(prefix="", tags=["Traveller Journeys & Saved Places"])


@router.get("/journeys", response_model=List[SavedJourneyResponse])
def get_saved_journeys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """Retrieve saved walking journey plans for the authenticated user."""
    journeys = db.query(SavedJourney).filter(
        SavedJourney.user_id == current_user.id
    ).order_by(desc(SavedJourney.saved_at)).all()

    return [
        SavedJourneyResponse(
            id=j.id,
            start=j.start,
            end=j.end,
            routeId=j.route_id,
            routeName=j.route_name,
            distanceMeters=j.distance_meters,
            durationMinutes=j.duration_minutes,
            preferences=j.preferences or {},
            savedAt=j.saved_at
        )
        for j in journeys
    ]


@router.post("/journeys", response_model=SavedJourneyResponse, status_code=status.HTTP_201_CREATED)
def save_journey_plan(
    payload: SavedJourneyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """Save a planned walking route to the traveller workspace."""
    journey = SavedJourney(
        user_id=current_user.id,
        start=payload.start.strip(),
        end=payload.end.strip(),
        route_id=payload.routeId.strip(),
        route_name=payload.routeName.strip(),
        distance_meters=payload.distanceMeters,
        duration_minutes=payload.durationMinutes,
        preferences=payload.preferences or {}
    )
    db.add(journey)
    db.commit()
    db.refresh(journey)

    record_audit_log(
        db=db,
        action="Saved Journey Plan",
        record=f"{journey.id}: {journey.start} -> {journey.end} ({journey.route_name})",
        actor=current_user.name,
        actor_id=current_user.id,
        actor_role=current_user.role
    )

    return SavedJourneyResponse(
        id=journey.id,
        start=journey.start,
        end=journey.end,
        routeId=journey.route_id,
        routeName=journey.route_name,
        distanceMeters=journey.distance_meters,
        durationMinutes=journey.duration_minutes,
        preferences=journey.preferences,
        savedAt=journey.saved_at
    )


@router.delete("/journeys/{journey_id}", response_model=GenericResponse)
def delete_saved_journey(
    journey_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """Delete a saved journey plan. Strictly prevents cross-user access (IDOR safe)."""
    journey = db.query(SavedJourney).filter(SavedJourney.id == journey_id).first()
    if not journey:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved journey not found.")
    if journey.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to delete another user's saved journey."
        )

    db.delete(journey)
    db.commit()

    record_audit_log(
        db=db,
        action="Deleted Journey Plan",
        record=journey_id,
        actor=current_user.name,
        actor_id=current_user.id,
        actor_role=current_user.role
    )

    return GenericResponse(status=200, message="Saved journey plan deleted.", success=True)


@router.get("/journeys/history", response_model=List[JourneyHistoryResponse])
def get_journey_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """Retrieve completed walk history for the authenticated traveller."""
    history = db.query(JourneyHistory).filter(
        JourneyHistory.user_id == current_user.id
    ).order_by(desc(JourneyHistory.completed_at)).all()

    return [
        JourneyHistoryResponse(
            id=h.id,
            origin=h.origin,
            destination=h.destination,
            routeChosen=h.route_chosen,
            completedAt=h.completed_at,
            durationMinutes=h.duration_minutes,
            arrivalConfirmed=h.arrival_confirmed,
            sharedWithCount=h.shared_with_count
        )
        for h in history
    ]


@router.get("/saved-places", response_model=List[SavedPlaceResponse])
def get_saved_places(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """List frequent origins and destinations for the authenticated traveller."""
    places = db.query(SavedPlace).filter(
        SavedPlace.user_id == current_user.id
    ).order_by(desc(SavedPlace.created_at)).all()

    return [
        SavedPlaceResponse(
            id=p.id,
            label=p.label,
            address=p.address,
            icon=p.icon,
            createdAt=p.created_at
        )
        for p in places
    ]


@router.post("/saved-places", response_model=SavedPlaceResponse, status_code=status.HTTP_201_CREATED)
def create_saved_place(
    payload: SavedPlaceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """Add a new saved place to the traveller's profile."""
    place = SavedPlace(
        user_id=current_user.id,
        label=payload.label.strip(),
        address=payload.address.strip(),
        icon=payload.icon
    )
    db.add(place)
    db.commit()
    db.refresh(place)

    return SavedPlaceResponse(
        id=place.id,
        label=place.label,
        address=place.address,
        icon=place.icon,
        createdAt=place.created_at
    )


@router.delete("/saved-places/{place_id}", response_model=GenericResponse)
def delete_saved_place(
    place_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """Delete a saved place (IDOR safe)."""
    place = db.query(SavedPlace).filter(SavedPlace.id == place_id).first()
    if not place:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved place not found.")
    if place.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to delete another user's saved place."
        )

    db.delete(place)
    db.commit()
    return GenericResponse(status=200, message="Saved place deleted.", success=True)
