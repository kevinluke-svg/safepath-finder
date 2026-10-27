from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, ConfigDict

ReportCategory = Literal[
    "broken_lighting",
    "blocked_footpath",
    "poor_visibility",
    "construction_hazard",
    "access_facility",
    "other_concern"
]

ReportStatus = Literal["pending", "approved", "rejected", "flagged"]


class ReportCreate(BaseModel):
    category: ReportCategory
    location: str = Field(..., min_length=2, max_length=255)
    description: str = Field(..., min_length=10, max_length=2000)
    anonymous: bool = False
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)


class ReportResponse(BaseModel):
    id: str
    category: str
    categoryLabel: str
    location: str
    description: str
    status: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    isAnonymous: bool = False
    reporterName: str
    provenance: str
    corroborations: int = 1
    moderatorNotes: str = ""
    createdAt: datetime
    updatedAt: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ReportModerationUpdate(BaseModel):
    status: ReportStatus
    reason: str = Field(..., min_length=2, max_length=500)


class ReportListResponse(BaseModel):
    items: List[ReportResponse]
    page: int
    pageSize: int
    total: int
