from __future__ import annotations

from typing import Any, Optional, Mapping
from uuid import UUID

from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorCollection

from app.domain.models import Feedback


class FeedbackRepository:
    """MongoDB repository for feedback documents.

    Collection: `feedbacks`.

    The Project -> Feedback relationship is 1:1 and is enforced by a unique index
    on `project_id`.

    Args:
        db: Motor database handle.
    """

    def __init__(self, db: AsyncIOMotorDatabase[Any]):
        """Initialize the repository.

        Args:
            db: Motor database handle.
        """
        self._col: AsyncIOMotorCollection[Mapping[str, Any]] = db["feedbacks"]

    async def ensure_indexes(self) -> None:
        """Create MongoDB indexes required by the application.

        Notes:
            Safe to call multiple times.
        """
        await self._col.create_index("project_id", unique=True)
        await self._col.create_index("created_at")
        await self._col.create_index("id", unique=True)

    async def get_by_project_id(self, project_id: UUID) -> Optional[Feedback]:
        """Fetch feedback by project id.

        Args:
            project_id: Project UUID.

        Returns:
            Feedback | None: Feedback if present.
        """
        doc: Mapping[str, Any] | None = await self._col.find_one({"project_id": str(project_id)})
        return Feedback.model_validate(doc) if doc else None

    async def upsert_for_project(self, feedback: Feedback) -> Feedback:
        """Create or update feedback for a project (1:1).

        If feedback for the given project already exists, its `id` is preserved and
        only the content is updated. Otherwise a new document is inserted.

        Args:
            feedback: Feedback model.

        Returns:
            Feedback: The stored feedback (with final id).
        """

        await self.ensure_indexes()

        existing: Feedback | None = await self.get_by_project_id(feedback.project_id)
        if existing is not None:
            feedback = feedback.model_copy(update={"id": existing.id})

        await self._col.update_one(
            {"project_id": str(feedback.project_id)},
            {"$set": feedback.model_dump(mode="json")},
            upsert=True,
        )
        return feedback
