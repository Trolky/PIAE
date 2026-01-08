from __future__ import annotations

from typing import Optional
from uuid import UUID

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.domain.enums import UserRole
from app.domain.models import User


class UserRepository:
    """MongoDB repository for users.

    This class is part of the data access layer and must be the only place where
    direct database queries for the `users` collection are performed.

    Args:
        db: Motor database handle.
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        """Initialize the repository.

        Args:
            db: Motor database handle.
        """
        self._col = db["users"]

    async def ensure_indexes(self) -> None:
        """Create MongoDB indexes required by the application.

        Notes:
            Safe to call multiple times.
        """
        await self._col.create_index("email_address", unique=True)
        await self._col.create_index("name", unique=True)
        await self._col.create_index("role")

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        """Fetch a user by id.

        Args:
            user_id: User UUID.

        Returns:
            User | None: Loaded user or None if not found.
        """
        doc = await self._col.find_one({"id": str(user_id)})
        return User.model_validate(doc) if doc else None

    async def get_by_email(self, email_address: str) -> Optional[User]:
        """Fetch a user by email.

        Args:
            email_address: Email address.

        Returns:
            User | None: Loaded user or None if not found.
        """
        doc = await self._col.find_one({"email_address": email_address})
        return User.model_validate(doc) if doc else None

    async def get_by_name(self, name: str) -> Optional[User]:
        """Fetch a user by username.

        Args:
            name: Alphanumeric username.

        Returns:
            User | None: Loaded user or None if not found.
        """
        doc = await self._col.find_one({"name": name})
        return User.model_validate(doc) if doc else None

    async def create(self, user: User) -> User:
        """Persist a new user.

        Args:
            user: User model.

        Returns:
            User: The same user instance.

        Raises:
            Any: Propagates underlying Motor/Mongo exceptions (e.g., duplicate key).
        """
        await self._col.insert_one(user.model_dump(mode="json"))
        return user

    async def list_by_ids(self, user_ids: list[UUID]) -> list[User]:
        """Load multiple users by ids.

        Args:
            user_ids: List of user UUIDs.

        Returns:
            list[User]: Users found for the given ids.
        """
        if not user_ids:
            return []
        ids = [str(x) for x in user_ids]
        cursor = self._col.find({"id": {"$in": ids}})
        docs = await cursor.to_list(length=len(ids))
        return [User.model_validate(d) for d in docs]

    async def map_ids_to_names(self, user_ids: list[UUID]) -> dict[str, str]:
        """Create an id->username mapping for a list of user ids.

        Args:
            user_ids: List of user UUIDs.

        Returns:
            dict[str, str]: Mapping {user_id: username}.
        """
        users = await self.list_by_ids(user_ids)
        return {str(u.id): u.name for u in users}

    async def list_translators_for_language(self, language_code: str) -> list[User]:
        """List translators (currently unfiltered) used as a building block.

        Args:
            language_code: Target language (ISO 639-1). Currently not used.

        Returns:
            list[User]: Translator users.
        """
        cursor = self._col.find({"role": UserRole.TRANSLATOR.value})
        docs = await cursor.to_list(length=1000)
        return [User.model_validate(d) for d in docs]

    async def enable_otp(self, *, user_id: UUID, otp_secret: str) -> None:
        """Enable OTP authentication for a user.

        Args:
            user_id: User UUID.
            otp_secret: Base32 TOTP secret.
        """
        await self._col.update_one(
            {"id": str(user_id)},
            {"$set": {"otp_enabled": True, "otp_secret": otp_secret}},
        )

    async def update_password_hash(self, *, user_id: UUID, password_hash: str) -> None:
        """Update stored password hash for a user.

        Args:
            user_id: User UUID.
            password_hash: New password hash.
        """
        await self._col.update_one(
            {"id": str(user_id)},
            {"$set": {"password_hash": password_hash}},
        )
