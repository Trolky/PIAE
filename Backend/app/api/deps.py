from __future__ import annotations

from typing import Any, Annotated, AsyncIterator, Optional

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from motor.motor_asyncio import AsyncIOMotorDatabase
from uuid import UUID

from app.db.mongo import get_db
from app.domain.models import User
from app.repositories.users import UserRepository
from app.security.jwt import decode_token


async def db_dep() -> AsyncIterator[AsyncIOMotorDatabase[Any]]:
    """FastAPI dependency that yields a MongoDB database handle.

    Yields:
        AsyncIOMotorDatabase: Database handle.
    """
    yield get_db()


Db: type(AsyncIOMotorDatabase) = Annotated[AsyncIOMotorDatabase[Any], Depends(db_dep)]

_security = HTTPBearer(auto_error=False)


async def current_user_dep(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_security),
    db: AsyncIOMotorDatabase[Any] = Depends(db_dep),
) -> User:
    """FastAPI dependency that resolves the currently authenticated user.

    The user is resolved by decoding a JWT token from the `Authorization: Bearer` header.

    Args:
        creds: Parsed HTTP bearer credentials.
        db: MongoDB database handle.

    Returns:
        User: Authenticated user.

    Raises:
        HTTPException: If token is missing/invalid or user does not exist.
    """
    if creds is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload: dict[str, Any] = decode_token(creds.credentials)
        user_id: UUID = UUID(payload.get("sub"))
    except (jwt.PyJWTError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid token")

    repo: UserRepository = UserRepository(db)
    user: User | None = await repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    return user


CurrentUser: type(User) = Annotated[User, Depends(current_user_dep)]
