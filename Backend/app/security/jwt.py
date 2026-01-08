from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import jwt as jwt_lib

from app.core.config import settings
from app.domain.enums import UserRole


def create_access_token(*, user_id: UUID, role: UserRole) -> str:
    """Create a signed JWT access token.

    Args:
        user_id: User UUID.
        role: User role.

    Returns:
        str: Encoded JWT.
    """
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=settings.jwt_access_token_exp_minutes)

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role.value,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }

    return jwt_lib.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token.

    Args:
        token: Encoded JWT.

    Returns:
        dict[str, Any]: Decoded payload.

    Raises:
        jwt.PyJWTError: If token is invalid or expired.
    """
    return jwt_lib.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
