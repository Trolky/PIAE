from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from app.domain.enums import ProjectState
from app.domain.models import Feedback, utc_now
from app.repositories.feedback import FeedbackRepository
from app.repositories.projects import ProjectRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReviewResult:
    """Result returned from a review action.

    Attributes:
        new_state: New project state.
    """

    new_state: ProjectState


class ProjectReviewService:
    """Customer review workflow for completed translations.

    Rules:
    - approve: COMPLETED -> APPROVED and store feedback (feedback text may be empty)
    - reject:  COMPLETED -> ASSIGNED and store feedback (feedback text must be non-empty)

    Feedback is stored in a separate collection and Project holds only `feedback_id`.

    Args:
        project_repo: Project repository.
        feedback_repo: Feedback repository.
    """

    def __init__(self, project_repo: ProjectRepository, feedback_repo: FeedbackRepository) -> None:
        """Initialize the service."""
        self._project_repo = project_repo
        self._feedback_repo = feedback_repo

    async def approve(self, *, project_id: UUID, customer_id: UUID, text: str = "") -> Optional[ReviewResult]:
        """Approve a completed translation.

        Args:
            project_id: Project UUID.
            customer_id: Customer UUID.
            text: Feedback text (optional).

        Returns:
            ReviewResult | None: Result with new_state, or None if state transition is not allowed.
        """
        fb = Feedback(project_id=project_id, text=text or "", created_at=utc_now())
        fb = await self._feedback_repo.upsert_for_project(fb)

        ok = await self._project_repo.set_feedback_and_state_if_customer(
            project_id=project_id,
            customer_id=customer_id,
            expected_state=ProjectState.COMPLETED.value,
            new_state=ProjectState.APPROVED.value,
            feedback_id=fb.id,
        )
        if not ok:
            return None

        logger.info(
            "Project approved",
            extra={"project_id": str(project_id), "customer_id": str(customer_id), "feedback_id": str(fb.id)},
        )
        return ReviewResult(new_state=ProjectState.APPROVED)

    async def reject(self, *, project_id: UUID, customer_id: UUID, text: str) -> Optional[ReviewResult]:
        """Reject a completed translation and provide feedback.

        Args:
            project_id: Project UUID.
            customer_id: Customer UUID.
            text: Feedback text (required).

        Returns:
            ReviewResult | None: Result with new_state, or None if state transition is not allowed.
        """
        if not (text or "").strip():
            return None

        fb = Feedback(project_id=project_id, text=text, created_at=utc_now())
        fb = await self._feedback_repo.upsert_for_project(fb)

        ok = await self._project_repo.set_feedback_and_state_if_customer(
            project_id=project_id,
            customer_id=customer_id,
            expected_state=ProjectState.COMPLETED.value,
            new_state=ProjectState.ASSIGNED.value,
            feedback_id=fb.id,
        )
        if not ok:
            return None

        logger.info(
            "Project rejected",
            extra={"project_id": str(project_id), "customer_id": str(customer_id), "feedback_id": str(fb.id)},
        )
        return ReviewResult(new_state=ProjectState.ASSIGNED)
