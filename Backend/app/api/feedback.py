from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from uuid import UUID

from app.api.deps import CurrentUser, Db
from app.domain.enums import UserRole
from app.domain.models import User
from app.repositories.feedback import FeedbackRepository
from app.repositories.projects import ProjectRepository

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackOut(BaseModel):
    """Feedback response model."""

    project_id: UUID
    text: str
    created_at: str


@router.get("/projects/{project_id}", response_model=FeedbackOut)
async def get_feedback_by_project(project_id: UUID, db=Db, current_user: User = CurrentUser) -> FeedbackOut:
    """Get feedback for a project.

    Access rules:
        - CUSTOMER: only own project
        - TRANSLATOR: only assigned project

    Args:
        project_id: Project UUID.
        db: MongoDB database dependency.
        current_user: Authenticated user.

    Returns:
        FeedbackOut: Feedback for the project.

    Raises:
        HTTPException: If project/feedback is not found or access is denied.
    """

    proj_repo = ProjectRepository(db)
    project = await proj_repo.get_by_id(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if current_user.role == UserRole.CUSTOMER and project.customer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")
    if current_user.role == UserRole.TRANSLATOR and project.translator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")

    repo = FeedbackRepository(db)
    feedback = await repo.get_by_project_id(project_id)
    if feedback is None:
        raise HTTPException(status_code=404, detail="Feedback not found")

    return FeedbackOut(project_id=feedback.project_id, text=feedback.text, created_at=feedback.created_at.isoformat())
