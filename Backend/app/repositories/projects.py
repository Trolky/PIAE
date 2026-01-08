from __future__ import annotations

from typing import Optional
from uuid import UUID

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.domain.models import Project


class ProjectRepository:
    """MongoDB repository for translation projects.

    This repository encapsulates all database queries for the `projects` collection.

    Args:
        db: Motor database handle.
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        """Initialize the repository.

        Args:
            db: Motor database handle.
        """
        self._col = db["projects"]

    async def ensure_indexes(self) -> None:
        """Create MongoDB indexes required by the application.

        Notes:
            Safe to call multiple times.
        """
        await self._col.create_index("id", unique=True)
        await self._col.create_index("customer_id")
        await self._col.create_index("translator_id")
        await self._col.create_index("state")
        await self._col.create_index("created_at")

    async def create(self, project: Project) -> Project:
        """Insert a new project.

        Args:
            project: Project model to persist.

        Returns:
            Project: The same project instance.
        """
        await self._col.insert_one(project.model_dump(mode="json"))
        return project

    async def get_by_id(self, project_id: UUID) -> Optional[Project]:
        """Fetch a project by id.

        Args:
            project_id: Project UUID.

        Returns:
            Project | None: Loaded project or None if not found.
        """
        doc = await self._col.find_one({"id": str(project_id)})
        return Project.model_validate(doc) if doc else None

    async def list_by_customer(self, customer_id: UUID) -> list[Project]:
        """List projects created by a customer.

        Args:
            customer_id: Customer UUID.

        Returns:
            list[Project]: Projects sorted by created_at DESC.
        """
        cursor = self._col.find({"customer_id": str(customer_id)}).sort("created_at", -1)
        docs = await cursor.to_list(length=200)
        return [Project.model_validate(d) for d in docs]

    async def assign_translator(self, project_id: UUID, translator_id: UUID, state: str) -> None:
        """Assign a translator to a project and update project state.

        Args:
            project_id: Project UUID.
            translator_id: Translator UUID.
            state: New state string (typically "ASSIGNED").
        """
        await self._col.update_one(
            {"id": str(project_id)},
            {"$set": {"translator_id": str(translator_id), "state": state}},
        )

    async def close_project(self, project_id: UUID) -> None:
        """Mark a project as CLOSED.

        Args:
            project_id: Project UUID.
        """
        await self._col.update_one({"id": str(project_id)}, {"$set": {"state": "CLOSED"}})

    async def list_by_translator(self, translator_id: UUID, *, include_closed: bool = False) -> list[Project]:
        """List projects assigned to a translator.

        Args:
            translator_id: Translator UUID.
            include_closed: Whether to include CLOSED projects.

        Returns:
            list[Project]: Projects sorted by created_at DESC.
        """
        query: dict[str, str] = {"translator_id": str(translator_id)}
        if not include_closed:
            query["state"] = {"$ne": "CLOSED"}
        cursor = self._col.find(query).sort("created_at", -1)
        docs = await cursor.to_list(length=200)
        return [Project.model_validate(d) for d in docs]

    async def count_active_by_translator_ids(self, translator_ids: list[UUID]) -> dict[str, int]:
        """Count non-CLOSED projects for multiple translators.

        Args:
            translator_ids: Translator UUIDs.

        Returns:
            dict[str, int]: Mapping {translator_id: active_project_count}.
        """
        if not translator_ids:
            return {}

        ids = [str(t) for t in translator_ids]
        pipeline = [
            {"$match": {"translator_id": {"$in": ids}, "state": {"$ne": "CLOSED"}}},
            {"$group": {"_id": "$translator_id", "count": {"$sum": 1}}},
        ]
        cursor = self._col.aggregate(pipeline)
        docs = await cursor.to_list(length=len(ids))

        counts: dict[str, int] = {str(t): 0 for t in translator_ids}
        for d in docs:
            counts[str(d.get("_id"))] = int(d.get("count") or 0)
        return counts

    async def submit_translation(self, *, project_id: UUID, translator_id: UUID, translated_file_id: str) -> bool:
        """Attach translated file id and switch state to COMPLETED.

        Args:
            project_id: Project UUID.
            translator_id: Translator UUID (must match project translator_id).
            translated_file_id: GridFS ObjectId (string).

        Returns:
            bool: True if the project was updated, False otherwise.
        """
        res = await self._col.update_one(
            {"id": str(project_id), "translator_id": str(translator_id)},
            {"$set": {"translated_file_id": translated_file_id, "state": "COMPLETED"}},
        )
        return bool(res.matched_count)

    async def set_state_if_customer(
        self,
        *,
        project_id: UUID,
        customer_id: UUID,
        expected_state: str,
        new_state: str,
    ) -> bool:
        """Update project state if the customer owns the project and state matches.

        Args:
            project_id: Project UUID.
            customer_id: Customer UUID.
            expected_state: Required current state.
            new_state: New state to set.

        Returns:
            bool: True if updated, False otherwise.
        """
        res = await self._col.update_one(
            {"id": str(project_id), "customer_id": str(customer_id), "state": expected_state},
            {"$set": {"state": new_state}},
        )
        return bool(res.matched_count)

    async def set_feedback_and_state_if_customer(
        self,
        *,
        project_id: UUID,
        customer_id: UUID,
        expected_state: str,
        new_state: str,
        feedback_id: UUID,
    ) -> bool:
        """Set feedback reference and update state if customer owns the project.

        Args:
            project_id: Project UUID.
            customer_id: Customer UUID.
            expected_state: Required current state.
            new_state: New state to set.
            feedback_id: Feedback UUID to reference.

        Returns:
            bool: True if updated, False otherwise.
        """
        res = await self._col.update_one(
            {"id": str(project_id), "customer_id": str(customer_id), "state": expected_state},
            {"$set": {"state": new_state, "feedback_id": str(feedback_id)}},
        )
        return bool(res.matched_count)
