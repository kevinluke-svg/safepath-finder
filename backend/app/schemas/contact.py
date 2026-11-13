from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class TrustedContactCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    relationship: str = Field(default="Friend", max_length=100)
    phone: str = Field(..., min_length=7, max_length=50, pattern=r"^\+?[0-9\s\-()]{7,25}$")


class TrustedContactUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    relationship: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, min_length=7, max_length=50, pattern=r"^\+?[0-9\s\-()]{7,25}$")
    notifyOnStart: Optional[bool] = None
    notifyOnArrival: Optional[bool] = None


class TrustedContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    relationship: str
    phone: str
    notifyOnStart: bool
    notifyOnArrival: bool
    createdAt: datetime




class JourneyShareRequest(BaseModel):
    routeName: str = Field(..., min_length=1)
    etaMinutes: int = Field(..., ge=1)
    destination: str = Field(..., min_length=2)
    contactIds: List[str] = Field(default_factory=list)


class JourneyShareResponse(BaseModel):
    deliveryStatus: str = "pending_provider_integration"
    providerName: str = "None configured (Backend integration required)"
    deliveredCount: int = 0
    intendedCount: int = 0
    shareLink: str
    previewMessage: str


class ArrivalConfirmationRequest(BaseModel):
    destination: str = Field(..., min_length=2)
    journeyId: str = Field(..., min_length=1)


class ArrivalConfirmationResponse(BaseModel):
    arrivalConfirmed: bool = True
    timestamp: datetime
    deliveryStatus: str = "pending_provider_integration"
    message: str


class JourneySessionStartRequest(BaseModel):
    origin: str = Field(..., min_length=2, max_length=255)
    destination: str = Field(..., min_length=2, max_length=255)
    routeName: str = Field(..., min_length=1, max_length=120)
    routeId: str = Field(..., min_length=1, max_length=64)
    etaMinutes: int = Field(..., ge=1, le=720)
    distanceMeters: Optional[int] = 0
    contactIds: List[str] = Field(default_factory=list)
    consentGiven: bool = Field(True, description="Explicit voluntary consent to share journey itinerary and ETA.")
    reminderMinutesBefore: Optional[int] = Field(5, ge=1, le=30)


class JourneySessionResponse(BaseModel):
    id: str
    token: str
    origin: str
    destination: str
    routeName: str
    routeId: str
    etaMinutes: int
    distanceMeters: int
    status: str  # active, completed, cancelled, overdue
    consentGiven: bool
    startedAt: datetime
    expectedArrivalAt: datetime
    completedAt: Optional[datetime] = None
    expiresAt: datetime
    isRevoked: bool
    contactCount: int
    shareUrl: str
    reminderMinutesBefore: int = 5
    notificationMode: str = "simulated_development"


class PublicJourneyShareView(BaseModel):
    token: str
    origin: str
    destination: str
    routeName: str
    etaMinutes: int
    distanceMeters: int
    status: str
    startedAt: datetime
    expectedArrivalAt: datetime
    completedAt: Optional[datetime] = None
    isOverdue: bool = False
    disclaimer: str = (
        "SafePath Peer-to-Peer Journey View. This tool does NOT dispatch emergency services or police. "
        "A missed check-in does not confirm an emergency; it alerts trusted contacts to check on traveller status."
    )
    peerReassuranceNotice: str = (
        "SafePath Peer-to-Peer Journey View. This tool does NOT dispatch emergency services or police. "
        "A missed check-in does not confirm an emergency; it alerts trusted contacts to check on traveller status."
    )

