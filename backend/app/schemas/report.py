from datetime import datetime, timezone
from typing import Optional, List, Literal, Any
from pydantic import BaseModel, Field, ConfigDict, model_validator, field_validator

ReportCategory = Literal[
    "broken_lighting",
    "blocked_footpath",
    "poor_visibility",
    "construction_hazard",
    "access_facility",
    "crossing_issue",
    "infrastructure_deficiency",
    "crime_incident",
    "other_concern",
    # Street Dog encounter categories (Priority 2)
    "dog_sighting",     # Ordinary, non-aggressive dog sighting
    "dog_group",        # Pack or group of dogs observed
    "dog_aggressive",   # Chasing, barking, or threatening behaviour
    "dog_bite"          # Bite or physical attack incident
]

ReportStatus = Literal["pending", "approved", "rejected", "flagged"]


class ReportCreate(BaseModel):
    category: ReportCategory
    location: str = Field(..., min_length=2, max_length=255)
    description: str = Field(..., min_length=10, max_length=2000)
    anonymous: bool = False
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    locationConfidence: Optional[str] = Field("user_pinned", max_length=30)
    encounterTime: Optional[datetime] = None
    dogCount: Optional[int] = Field(None, ge=1, le=50)
    isAggressive: Optional[bool] = None

    @model_validator(mode="before")
    @classmethod
    def map_snake_case(cls, data: Any) -> Any:
        if isinstance(data, dict):
            d = dict(data)
            if "dog_count" in d and "dogCount" not in d:
                d["dogCount"] = d["dog_count"]
            if "is_aggressive" in d and "isAggressive" not in d:
                d["isAggressive"] = d["is_aggressive"]
            if "location_confidence" in d and "locationConfidence" not in d:
                d["locationConfidence"] = d["location_confidence"]
            if "encounter_time" in d and "encounterTime" not in d:
                d["encounterTime"] = d["encounter_time"]
            if "observed_at" in d and "encounterTime" not in d:
                d["encounterTime"] = d["observed_at"]
            if "observedAt" in d and "encounterTime" not in d:
                d["encounterTime"] = d["observedAt"]
            return d
        return data


class ReportUpdate(BaseModel):
    category: Optional[ReportCategory] = None
    location: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = Field(None, min_length=10, max_length=2000)
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    locationConfidence: Optional[str] = Field(None, max_length=30)
    encounterTime: Optional[datetime] = None
    dogCount: Optional[int] = Field(None, ge=1, le=50)
    isAggressive: Optional[bool] = None

    @model_validator(mode="before")
    @classmethod
    def map_snake_case(cls, data: Any) -> Any:
        if isinstance(data, dict):
            d = dict(data)
            if "dog_count" in d and "dogCount" not in d:
                d["dogCount"] = d["dog_count"]
            if "is_aggressive" in d and "isAggressive" not in d:
                d["isAggressive"] = d["is_aggressive"]
            if "location_confidence" in d and "locationConfidence" not in d:
                d["locationConfidence"] = d["location_confidence"]
            if "encounter_time" in d and "encounterTime" not in d:
                d["encounterTime"] = d["encounter_time"]
            return d
        return data


class ReportResponse(BaseModel):
    id: str
    category: str
    categoryLabel: str
    location: str
    description: str
    status: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    locationConfidence: str = "user_pinned"
    duplicateOfId: Optional[str] = None
    isAnonymous: bool = False
    reporterName: str
    provenance: str
    corroborations: int = 1
    outdatedFlags: int = 0
    moderatorNotes: str = ""
    encounterTime: Optional[datetime] = None
    dogCount: Optional[int] = None
    isAggressive: Optional[bool] = None
    createdAt: datetime
    updatedAt: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CorroborationResponse(BaseModel):
    message: str
    reportId: str
    corroborationsCount: int
    userHasCorroborated: bool


class ReportFeedbackResponse(BaseModel):
    message: str
    reportId: str
    action: str  # "confirm_present" or "flag_outdated"
    corroborationsCount: int
    outdatedFlagsCount: int
    userActionRecorded: bool


class ReportModerationUpdate(BaseModel):
    status: ReportStatus
    reason: str = Field(..., min_length=2, max_length=500)


class ReportListResponse(BaseModel):
    items: List[ReportResponse]
    page: int
    pageSize: int
    total: int
