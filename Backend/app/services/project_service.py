from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional
from uuid import UUID, uuid4

from fastapi import HTTPException

from app.core.config import settings
from app.db.gridfs import GridFsService
from app.domain.enums import UserRole
from app.domain.models import Project, User
from app.repositories.projects import ProjectRepository
from app.repositories.translator_languages import TranslatorLanguageRepository
from app.repositories.users import UserRepository
from app.services.assignment import ProjectAssignmentService
from app.services.emailer import EmailService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CreateProjectResult:
    """Result returned from project creation workflow.

    Attributes:
        project: Persisted project model (including updated state/translator_id).
        assigned_translator_id: Translator id if assigned, otherwise None.
    """

    project: Project
    assigned_translator_id: Optional[UUID]


class ProjectService:
    """Project application service.

    This service orchestrates the project creation workflow:
    1) validate role & upload size
    2) upload original file to GridFS
    3) create project in MongoDB
    4) assign translator (or close the project)
    5) send email notification

    Args:
        project_repo: Project repository.
        translator_lang_repo: TranslatorLanguage repository.
        user_repo: User repository.
        gridfs: GridFS helper.
        mailer: Email service.
    """

    def __init__(
        self,
        *,
        project_repo: ProjectRepository,
        translator_lang_repo: TranslatorLanguageRepository,
        user_repo: UserRepository,
        gridfs: GridFsService,
        mailer: EmailService,
    ) -> None:
        """Initialize the service.

        Args:
            project_repo: Project repository.
            translator_lang_repo: TranslatorLanguage repository.
            user_repo: User repository.
            gridfs: GridFS helper.
            mailer: Email service.
        """
        self._project_repo = project_repo
        self._translator_lang_repo = translator_lang_repo
        self._user_repo = user_repo
        self._gridfs = gridfs
        self._mailer = mailer

    async def create_project(
        self,
        *,
        customer: User,
        language_code: str,
        original_filename: str,
        content_type: str,
        content: bytes,
    ) -> CreateProjectResult:
        """Create a new project and run the assignment workflow.

        Args:
            customer: Authenticated customer user.
            language_code: Target language (ISO 639-1).
            original_filename: Uploaded filename.
            content_type: Uploaded file content type.
            content: File bytes.

        Returns:
            CreateProjectResult: Created project and assignment result.

        Raises:
            HTTPException: If the user role is not CUSTOMER or file is too large.
        """
        if customer.role != UserRole.CUSTOMER:
            raise HTTPException(status_code=403, detail="Only customers can create projects")

        max_bytes = settings.max_upload_mb * 1024 * 1024
        if len(content) > max_bytes:
            raise HTTPException(status_code=413, detail=f"Max upload size is {settings.max_upload_mb} MB")

        # 1) upload do GridFS
        file_id = await self._gridfs.upload(
            filename=original_filename or "upload.bin",
            data=content,
            metadata={"content_type": content_type or "application/octet-stream"},
        )

        # 2) vytvoření projektu
        project = Project(
            id=uuid4(),
            customer_id=customer.id,
            translator_id=None,
            language_code=language_code.lower(),
            original_file_id=str(file_id),
        )

        await self._project_repo.ensure_indexes()
        await self._project_repo.create(project)

        logger.info(
            "Project created",
            extra={
                "project_id": str(project.id),
                "customer_id": str(customer.id),
                "language_code": project.language_code,
                "original_file_id": project.original_file_id,
            },
        )

        # 3) přiřazení / uzavření (FR2)
        assignment = ProjectAssignmentService(self._project_repo, self._translator_lang_repo)
        translator_id = await assignment.assign_or_close(project.id, project.language_code)

        # 4) email notifikace (FR2)
        if translator_id is not None:
            translator = await self._user_repo.get_by_id(translator_id)
            if translator is not None:
                self._mailer.send(
                    to=str(translator.email_address),
                    subject="New translation project assigned",
                    text=(
                        f"Hi {translator.name},\n\n"
                        f"A new project was assigned to you.\n"
                        f"Project ID: {project.id}\n"
                        f"Target language: {project.language_code}\n"
                    ),
                )
        else:
            refreshed_customer = await self._user_repo.get_by_id(customer.id)
            if refreshed_customer is not None:
                self._mailer.send(
                    to=str(refreshed_customer.email_address),
                    subject="Project closed - no translator available",
                    text=(
                        f"Hi {refreshed_customer.name},\n\n"
                        f"We couldn't find a translator for language '{project.language_code}'.\n"
                        f"Your project has been closed.\n"
                        f"Project ID: {project.id}\n"
                    ),
                )

        stored = await self._project_repo.get_by_id(project.id)
        assert stored is not None
        return CreateProjectResult(project=stored, assigned_translator_id=translator_id)
