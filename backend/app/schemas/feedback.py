from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, ConfigDict

FeedbackCategory = Literal["routing_quality", "lighting_accuracy", "app_bug", "safety_concern", "general"]
FeedbackStatus = Literal["new", "under_review", "resolved", "archived"]


class FeedbackCreate(BaseModel):
    category: FeedbackCategory = "general"
    message: str = Field(..., min_length=5, max_length=2000, description="Constructive feedback or bug description")
    rating: Optional[int] = Field(None, ge=1, le=5, description="Optional satisfaction rating from 1 to 5")


class FeedbackResponse(BaseModel):
    id: str
    category: str
    message: str
    rating: Optional[int] = None
    status: str
    createdAt: datetime
    isAnonymous: bool = True

    model_config = ConfigDict(from_attributes=True)


class AdminFeedbackResponse(BaseModel):
    id: str
    userId: Optional[str] = None
    category: str
    message: str
    rating: Optional[int] = None
    status: str
    createdAt: datetime
    adminNotes: Optional[str] = None
    reviewedBy: Optional[str] = None
    reviewedAt: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AdminFeedbackListResponse(BaseModel):
    items: List[AdminFeedbackResponse]
    page: int
    pageSize: int
    total: int


class AdminFeedbackUpdate(BaseModel):
    status: FeedbackStatus
    adminNotes: Optional[str] = Field(None, max_length=1000)
