from datetime import datetime
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict


class SavedJourneyCreate(BaseModel):
    start: str = Field(..., min_length=2, max_length=255)
    end: str = Field(..., min_length=2, max_length=255)
    routeId: str = Field(..., min_length=2, max_length=64)
    routeName: str = Field(..., min_length=2, max_length=120)
    distanceMeters: int = Field(..., ge=1)
    durationMinutes: int = Field(..., ge=1)
    preferences: Dict[str, Any] = Field(default_factory=dict)


class SavedJourneyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    start: str
    end: str
    routeId: str
    routeName: str
    distanceMeters: int
    durationMinutes: int
    preferences: Dict[str, Any]
    savedAt: datetime


class JourneyHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    origin: str
    destination: str
    routeChosen: str
    completedAt: datetime
    durationMinutes: int
    arrivalConfirmed: bool
    sharedWithCount: int


class SavedPlaceCreate(BaseModel):
    label: str = Field(..., min_length=1, max_length=100)
    address: str = Field(..., min_length=2, max_length=255)
    icon: str = "place"


class SavedPlaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    label: str
    address: str
    icon: str
    createdAt: datetime

