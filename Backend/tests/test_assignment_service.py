from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.services.assignment import ProjectAssignmentService


class _ProjectRepoFake:
    """In-memory fake of ProjectRepository for assignment tests.

    This fake provides:
        - `count_active_by_translator_ids` to simulate translator load
        - `assign_translator` and `close_project` to record side effects

    Args:
        counts: Optional mapping {translator_id: active_project_count}.
    """

    def __init__(self, *, counts: dict[str, int] | None = None) -> None:
        self.counts = counts or {}
        self.assigned: list[tuple[str, str, str]] = []
        self.closed: list[str] = []

    async def count_active_by_translator_ids(self, translator_ids: list[UUID]) -> dict[str, int]:
        """Return active project counts for the given translators.

        Args:
            translator_ids: Translator UUIDs.

        Returns:
            dict[str, int]: Mapping {translator_id: active_project_count}.
        """
        return {str(t): int(self.counts.get(str(t), 0)) for t in translator_ids}

    async def assign_translator(self, project_id: UUID, translator_id: UUID, state: str) -> None:
        """Record assignment side effect."""
        self.assigned.append((str(project_id), str(translator_id), state))

    async def close_project(self, project_id: UUID) -> None:
        """Record closing side effect."""
        self.closed.append(str(project_id))


class _TranslatorLangRepoFake:
    """Fake TranslatorLanguageRepository returning a predefined translator list."""

    def __init__(self, ids: list[str]):
        self._ids = ids

    async def list_translator_ids_for_language(self, language_code: str) -> list[str]:
        """Return translator ids that support the requested language."""
        return self._ids


@pytest.mark.asyncio
async def test_assign_or_close_picks_least_loaded_translator() -> None:
    """Assignment should pick the least loaded translator.

    Scenario:
        Translators t1/t2/t3 all support the language, with counts:
        - t1: 5 active
        - t2: 1 active
        - t3: 1 active

    Expected behavior:
        - Service assigns a translator (does not close the project).
        - The chosen translator is the one with minimum active count.
        - If multiple translators tie, the repository order is respected.
    """

    project_id = uuid4()
    t1 = uuid4()
    t2 = uuid4()
    t3 = uuid4()

    project_repo = _ProjectRepoFake(counts={str(t1): 5, str(t2): 1, str(t3): 1})
    svc = ProjectAssignmentService(
        project_repo,  # type: ignore[arg-type]
        _TranslatorLangRepoFake([str(t1), str(t2), str(t3)]),  # type: ignore[arg-type]
    )

    chosen = await svc.assign_or_close(project_id, "cs")

    assert chosen == t2
    assert project_repo.assigned
    assert project_repo.assigned[0][1] == str(t2)
    assert project_repo.closed == []


@pytest.mark.asyncio
async def test_assign_or_close_closes_when_no_translator() -> None:
    """Assignment should close the project when no translator supports the language.

    Scenario:
        No translator ids are returned for the language.

    Expected behavior:
        - Service closes the project.
        - Returned translator id is None.
    """

    project_id = uuid4()
    project_repo = _ProjectRepoFake()

    svc = ProjectAssignmentService(
        project_repo,  # type: ignore[arg-type]
        _TranslatorLangRepoFake([]),  # type: ignore[arg-type]
    )

    chosen = await svc.assign_or_close(project_id, "cs")
    assert chosen is None
    assert project_repo.closed == [str(project_id)]
