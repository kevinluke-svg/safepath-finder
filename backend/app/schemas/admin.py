from datetime import datetime
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict

UserRole = Literal["traveller", "moderator", "administrator"]


class UserRoleUpdate(BaseModel):
    role: UserRole


class AdminUserResponse(BaseModel):
    """Privacy-minimized user record for ordinary administrative directory view."""
    id: str
    displayName: str
    emailMasked: str
    role: str
    status: str
    joinedAt: datetime
    reportsCount: int = 0
    savedPlansCount: int = 0

    model_config = ConfigDict(from_attributes=True)


class AdminIdentityRevealRequest(BaseModel):
    """Audit requirement for accessing private user identity details."""
    reason: str = Field(..., min_length=5, max_length=500, description="Audit justification for accessing sensitive identity data")


class AdminUserIdentityResponse(BaseModel):
    """Permission-gated sensitive identity details for authorized account support."""
    id: str
    name: str
    email: str
    role: str
    status: str
    joinedAt: datetime
    revealedAt: datetime
    revealedBy: str
    justification: str

    model_config = ConfigDict(from_attributes=True)


class AdminUserListResponse(BaseModel):
    items: List[AdminUserResponse]
    page: int
    pageSize: int
    total: int



class AuditLogResponse(BaseModel):
    id: str
    timestamp: datetime
    action: str
    record: str
    actor: str
    actorRole: str
    outcome: str
    environment: str

    model_config = ConfigDict(from_attributes=True)


class AuditLogListResponse(BaseModel):
    items: List[AuditLogResponse]
    total: int


class SystemSettingResponse(BaseModel):
    freshnessThresholdDays: int
    outdatedThresholdDays: int
    autoFlagKeywords: str
    requireModeratorApproval: bool
    evidenceWeightLighting: int
    evidenceWeightActivity: int
    timeWeight: int

    model_config = ConfigDict(from_attributes=True)


class SystemSettingUpdate(BaseModel):
    freshnessThresholdDays: Optional[int] = Field(None, ge=7, le=180)
    outdatedThresholdDays: Optional[int] = Field(None, ge=30, le=365)
    autoFlagKeywords: Optional[str] = None
    requireModeratorApproval: Optional[bool] = None
    evidenceWeightLighting: Optional[int] = Field(None, ge=0, le=100)
    evidenceWeightActivity: Optional[int] = Field(None, ge=0, le=100)
    timeWeight: Optional[int] = Field(None, ge=0, le=100)
