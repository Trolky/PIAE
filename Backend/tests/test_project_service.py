from __future__ import annotations

from uuid import UUID

import pytest

from app.domain.enums import ProjectState, UserRole
from app.domain.models import User
from app.services.project_service import ProjectService


class _ProjectRepoFake:
    def __init__(self) -> None:
        self.created = []
        self.assigned: list[tuple[str, str, str]] = []
        self.closed: list[str] = []
        self._stored: dict[str, object] = {}

    async def ensure_indexes(self) -> None:
        return None

    async def create(self, project):
        self.created.append(project)
        self._stored[str(project.id)] = project
        return project

    async def get_by_id(self, project_id: UUID):
        return self._stored.get(str(project_id))

    async def close_project(self, project_id: UUID) -> None:
        p = self._stored.get(str(project_id))
        if p:
            p.state = ProjectState.CLOSED
        self.closed.append(str(project_id))

    async def assign_translator(self, project_id: UUID, translator_id: UUID, state: str) -> None:
        p = self._stored.get(str(project_id))
        if p:
            p.translator_id = translator_id
            p.state = ProjectState(state)
        self.assigned.append((str(project_id), str(translator_id), state))


class _TranslatorLangRepoFake:
    def __init__(self, ids: list[str]):
        self._ids = ids

    async def list_translator_ids_for_language(self, language_code: str) -> list[str]:
        return self._ids


class _UserRepoFake:
    def __init__(self, by_id: dict[str, User]):
        self._by_id = by_id

    async def get_by_id(self, user_id: UUID):
        return self._by_id.get(str(user_id))


class _GridFsFake:
    def __init__(self, file_id: str = "507f1f77bcf86cd799439011"):
        self.file_id = file_id
        self.uploaded: list[tuple[str, bytes, dict]] = []

    async def upload(self, *, filename: str, data: bytes, metadata: dict | None = None):
        self.uploaded.append((filename, data, metadata or {}))
        # ObjectId-like string
        return self.file_id


class _EmailFake:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send(self, *, to: str, subject: str, text: str) -> None:
        self.sent.append({"to": to, "subject": subject, "text": text})


@pytest.mark.asyncio
async def test_project_service_creates_and_assigns_when_translator_exists():
    customer = User.model_validate({"id": UUID("00000000-0000-0000-0000-000000000001"), "name": "cust", "email_address": "c@x.com", "role": UserRole.CUSTOMER, "password_hash": "x"})
    translator = User.model_validate({"id": UUID("00000000-0000-0000-0000-000000000002"), "name": "tr", "email_address": "t@x.com", "role": UserRole.TRANSLATOR, "password_hash": "x"})

    project_repo = _ProjectRepoFake()
    tl_repo = _TranslatorLangRepoFake([str(translator.id)])
    user_repo = _UserRepoFake({str(customer.id): customer, str(translator.id): translator})
    fs = _GridFsFake()
    mailer = _EmailFake()

    svc = ProjectService(
        project_repo=project_repo,  # type: ignore[arg-type]
        translator_lang_repo=tl_repo,  # type: ignore[arg-type]
        user_repo=user_repo,  # type: ignore[arg-type]
        gridfs=fs,  # type: ignore[arg-type]
        mailer=mailer,  # type: ignore[arg-type]
    )

    res = await svc.create_project(
        customer=customer,
        language_code="cs",
        original_filename="a.txt",
        content_type="text/plain",
        content=b"hello",
    )

    assert res.project.customer_id == customer.id
    assert res.assigned_translator_id == translator.id
    assert res.project.state == ProjectState.ASSIGNED
    assert mailer.sent and mailer.sent[0]["to"] == "t@x.com"


@pytest.mark.asyncio
async def test_project_service_closes_when_no_translator():
    customer = User.model_validate({"id": UUID("00000000-0000-0000-0000-000000000001"), "name": "cust", "email_address": "c@x.com", "role": UserRole.CUSTOMER, "password_hash": "x"})

    project_repo = _ProjectRepoFake()
    tl_repo = _TranslatorLangRepoFake([])
    user_repo = _UserRepoFake({str(customer.id): customer})
    fs = _GridFsFake()
    mailer = _EmailFake()

    svc = ProjectService(
        project_repo=project_repo,  # type: ignore[arg-type]
        translator_lang_repo=tl_repo,  # type: ignore[arg-type]
        user_repo=user_repo,  # type: ignore[arg-type]
        gridfs=fs,  # type: ignore[arg-type]
        mailer=mailer,  # type: ignore[arg-type]
    )

    res = await svc.create_project(
        customer=customer,
        language_code="cs",
        original_filename="a.txt",
        content_type="text/plain",
        content=b"hello",
    )

    assert res.assigned_translator_id is None
    assert res.project.state == ProjectState.CLOSED
    # email zákazníkovi
    assert mailer.sent and mailer.sent[0]["to"] == "c@x.com"
