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
