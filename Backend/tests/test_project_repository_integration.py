from __future__ import annotations

import os
from uuid import uuid4

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from app.domain.models import Project
from app.repositories.projects import ProjectRepository


@pytest.mark.asyncio
async def test_project_repository_create_and_get() -> None:
    """ProjectRepository should persist and load a project (integration).

    This test touches a real MongoDB instance.

    Environment:
        - MONGODB_URI (default: mongodb://localhost:27017)
        - MONGODB_DB (default: piae_test)

    Expected behavior:
        - `create()` writes a document with expected fields.
        - `get_by_id()` returns the created project.
    """

    mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    db_name = os.getenv("MONGODB_DB", "piae_test")

    client = AsyncIOMotorClient(mongodb_uri)
    db = client[db_name]

    repo = ProjectRepository(db)
    await repo.ensure_indexes()

    project_id = uuid4()
    customer_id = uuid4()

    project = Project(
        id=project_id,
        customer_id=customer_id,
        language_code="cs",
        original_file_id="dummy",
    )

    await repo.create(project)

    raw = await db["projects"].find_one({"id": str(project_id)})
    assert raw is not None
    assert raw["id"] == str(project_id)
    assert raw["customer_id"] == str(customer_id)
    assert raw["original_file_id"] == "dummy"

    loaded = await repo.get_by_id(project_id)
    assert loaded is not None
    assert loaded.id == project_id
    assert loaded.original_file_id == "dummy"

    await db["projects"].delete_many({"id": str(project_id)})
    client.close()
