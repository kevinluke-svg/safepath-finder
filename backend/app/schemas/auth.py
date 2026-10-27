from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class UserBase(BaseModel):
    email: str = Field(..., pattern=EMAIL_PATTERN, max_length=255)
    name: str = Field(..., min_length=1, max_length=120)


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: str = Field(..., pattern=EMAIL_PATTERN)
    password: str = Field(..., min_length=1)


class UserResponse(UserBase):
    id: str
    role: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    accessToken: str
    tokenType: str = "bearer"
    user: UserResponse


class PasswordResetRequest(BaseModel):
    email: str = Field(..., pattern=EMAIL_PATTERN)


class PasswordResetConfirm(BaseModel):
    token: str = Field(..., min_length=4)
    password: str = Field(..., min_length=8, max_length=128)


class GenericResponse(BaseModel):
    status: int = 200
    message: str
    success: bool = True
