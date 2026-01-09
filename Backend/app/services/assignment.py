from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from app.domain.enums import ProjectState
from app.repositories.projects import ProjectRepository
from app.repositories.translator_languages import TranslatorLanguageRepository

logger = logging.getLogger(__name__)


class ProjectAssignmentService:
    """Select and assign a translator for a project.

    This service implements:
    - select translators who support `language_code`
    - pick the translator with the lowest number of active (non-CLOSED) projects
    - if multiple translators tie, pick the first one in the repository order
    - if no translator exists, close the project

    Args:
        project_repo: Project repository.
        translator_lang_repo: TranslatorLanguage repository.
    """

    def __init__(
        self,
        project_repo: ProjectRepository,
        translator_lang_repo: TranslatorLanguageRepository,
    ):
        self._project_repo: ProjectRepository = project_repo
        self._translator_lang_repo: TranslatorLanguageRepository = translator_lang_repo

    async def find_best_translator_id(self, language_code: str) -> Optional[UUID]:
        """Find the best translator for a language.

        Args:
            language_code: Target language (ISO 639-1).

        Returns:
            UUID | None: Chosen translator id, or None if none is available.
        """

        translator_ids_raw: list[str] = await self._translator_lang_repo.list_translator_ids_for_language(language_code)
        if not translator_ids_raw:
            return None

        translator_ids: list[UUID] = [UUID(x) for x in translator_ids_raw]
        counts: dict[str, int] = await self._project_repo.count_active_by_translator_ids(translator_ids)

        best: Optional[UUID] = None
        best_count: Optional[int] = None
        for tid in translator_ids:
            c = counts.get(str(tid), 0)
            if best is None or best_count is None or c < best_count:
                best = tid
                best_count = c

        return best

    async def assign_or_close(self, project_id: UUID, language_code: str) -> Optional[UUID]:
        """Assign a translator to a project or close it.

        Args:
            project_id: Project UUID.
            language_code: Target language (ISO 639-1).

        Returns:
            UUID | None: Assigned translator id, or None if the project was closed.
        """

        translator_id: UUID | None = await self.find_best_translator_id(language_code)
        if translator_id is None:
            await self._project_repo.close_project(project_id)
            logger.info(
                "No translator found; project closed",
                extra={"project_id": str(project_id), "language_code": language_code},
            )
            return None

        await self._project_repo.assign_translator(
            project_id=project_id,
            translator_id=translator_id,
            state=ProjectState.ASSIGNED.value,
        )
        logger.info(
            "Project assigned",
            extra={"project_id": str(project_id), "translator_id": str(translator_id)},
        )
        return translator_id
