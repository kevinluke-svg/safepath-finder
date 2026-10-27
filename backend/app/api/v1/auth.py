from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.core.security import get_password_hash, verify_password, create_access_token
from app.models.user import User
from app.schemas.auth import (
    UserCreate, UserLogin, UserResponse, Token,
    PasswordResetRequest, PasswordResetConfirm, GenericResponse
)
from app.services.audit_service import record_audit_log

router = APIRouter(prefix="", tags=["Identity & Authentication"])


@router.post("/auth/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, db: Session = Depends(get_db)) -> Any:
    """Register a new traveller account with Argon2id password hashing."""
    existing_user = db.query(User).filter(User.email == user_in.email.lower()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists.",
        )

    user = User(
        name=user_in.name.strip(),
        email=user_in.email.lower(),
        hashed_password=get_password_hash(user_in.password),
        role="traveller",
        status="active"
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(subject=user.id, role=user.role)
    record_audit_log(
        db=db,
        action="User Registered",
        record=f"{user.name} ({user.email})",
        actor=user.name,
        actor_id=user.id,
        actor_role=user.role
    )

    return Token(accessToken=token, tokenType="bearer", user=UserResponse.model_validate(user))


@router.post("/auth/login", response_model=Token)
def login(credentials: UserLogin, db: Session = Depends(get_db)) -> Any:
    """Authenticate with email and password, issuing a signed JWT."""
    user = db.query(User).filter(User.email == credentials.email.lower()).first()
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.status == "suspended":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been suspended.",
        )

    token = create_access_token(subject=user.id, role=user.role)
    record_audit_log(
        db=db,
        action="User Sign In",
        record=f"Session established for {user.email}",
        actor=user.name,
        actor_id=user.id,
        actor_role=user.role
    )

    return Token(accessToken=token, tokenType="bearer", user=UserResponse.model_validate(user))


from app.services import password_reset_service


@router.post("/auth/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
def request_password_reset(payload: PasswordResetRequest, db: Session = Depends(get_db)) -> Any:
    """
    Request password recovery. Per API contract and privacy invariants, always returns 202
    without revealing whether an account exists, preventing user enumeration attacks.
    """
    password_reset_service.request_password_reset(db=db, email=payload.email)
    return {
        "status": 202,
        "message": "If an account matches that email address, password reset instructions have been dispatched."
    }


@router.post("/auth/password-reset/confirm", response_model=GenericResponse)
def confirm_password_reset(payload: PasswordResetConfirm, db: Session = Depends(get_db)) -> Any:
    """
    Confirm password reset with a valid single-use token.
    Updates password using Argon2id and invalidates the token.
    """
    password_reset_service.confirm_password_reset(
        db=db,
        raw_token=payload.token,
        new_password=payload.password
    )

    return GenericResponse(
        status=200,
        message="Password has been reset successfully. You may now sign in with your new credentials.",
        success=True
    )



@router.post("/auth/logout", response_model=GenericResponse)
def logout(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Any:
    """Sign out the current authenticated user."""
    record_audit_log(
        db=db,
        action="User Sign Out",
        record=f"Session closed for {current_user.email}",
        actor=current_user.name,
        actor_id=current_user.id,
        actor_role=current_user.role
    )
    return GenericResponse(status=200, message="Signed out successfully.", success=True)


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(current_user: User = Depends(get_current_user)) -> Any:
    """Retrieve profile and role information for the authenticated user."""
    return UserResponse.model_validate(current_user)
