from __future__ import annotations

import hmac
import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, Db
from app.domain.models import User
from app.repositories.users import UserRepository
from app.security.jwt import create_access_token
from app.services.otp import generate_secret, provisioning_uri_from_secret, verify_totp_secret
from app.security.passwords import verify_password, hash_password, needs_rehash

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    """Request body for password-based login.

    Attributes:
        username: Alphanumeric username.
        password: Plaintext password (preferred).
    """

    username: str = Field(min_length=1, pattern=r"^[A-Za-z0-9]+$")
    password: str | None = Field(default=None, min_length=1, description="Plaintext password")


class OtpProvisionOut(BaseModel):
    """Response model containing an otpauth provisioning URI."""

    otpauth_uri: str


class OtpLoginIn(BaseModel):
    """Request body for OTP (TOTP) login."""

    username: str = Field(min_length=1, pattern=r"^[A-Za-z0-9]+$")
    otp: str = Field(min_length=4, max_length=12)


class TokenOut(BaseModel):
    """JWT token response returned after successful authentication."""

    access_token: str
    token_type: str = "bearer"
    user_id: UUID
    role: str


@router.post("/login", response_model=TokenOut)
async def login(payload: LoginIn, db=Db) -> TokenOut:
    """Authenticate a user and return a JWT access token.

    Args:
        payload: Login payload.
        db: MongoDB database dependency.

    Returns:
        TokenOut: Access token and basic user info.

    Raises:
        HTTPException: If credentials are invalid or payload is incomplete.
    """

    repo = UserRepository(db)
    user = await repo.get_by_name(payload.username)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if payload.password is not None:
        if not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        if needs_rehash(user.password_hash):
            try:
                await repo.update_password_hash(user_id=user.id, password_hash=hash_password(payload.password))
            except Exception:
                pass
    else:
        if not hmac.compare_digest(user.password_hash, payload.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(user_id=user.id, role=user.role)
    logger.info("User logged in", extra={"user_id": str(user.id), "role": user.role.value})

    return TokenOut(access_token=token, user_id=user.id, role=user.role.value)


@router.post("/otp/enable", response_model=OtpProvisionOut)
async def otp_enable(db=Db, current_user: User = CurrentUser) -> OtpProvisionOut:
    """Enable OTP (TOTP) for the currently authenticated user.

    This endpoint requires a valid JWT (password login first). It stores a new
    per-user TOTP secret and returns an otpauth provisioning URI.

    Args:
        db: MongoDB database dependency.
        current_user: Authenticated user.

    Returns:
        OtpProvisionOut: Provisioning URI.
    """

    repo = UserRepository(db)

    secret = generate_secret()
    await repo.enable_otp(user_id=current_user.id, otp_secret=secret)

    uri = provisioning_uri_from_secret(secret=secret, username=current_user.name)
    logger.info("OTP enabled", extra={"user_id": str(current_user.id)})
    return OtpProvisionOut(otpauth_uri=uri)


@router.post("/otp/login", response_model=TokenOut)
async def otp_login(payload: OtpLoginIn, db=Db) -> TokenOut:
    """Authenticate using OTP (TOTP) and return a JWT token.

    Args:
        payload: OTP login payload.
        db: MongoDB database dependency.

    Returns:
        TokenOut: Access token and basic user info.

    Raises:
        HTTPException: If credentials are invalid.
    """

    repo = UserRepository(db)
    user = await repo.get_by_name(payload.username)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not getattr(user, "otp_enabled", False) or not getattr(user, "otp_secret", None):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_totp_secret(secret=str(user.otp_secret), code=payload.otp):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(user_id=user.id, role=user.role)
    logger.info("User OTP logged in", extra={"user_id": str(user.id), "role": user.role.value})

    return TokenOut(access_token=token, user_id=user.id, role=user.role.value)
