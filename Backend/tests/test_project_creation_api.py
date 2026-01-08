from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_project_requires_customer_role(monkeypatch):
    """Ověří, že /projects POST je chráněný a jen pro CUSTOMER."""

    from app.api import deps
    from app.domain.enums import UserRole

    class _User:
        def __init__(self, role):
            self.id = uuid4()
            self.role = role

    async def _fake_current_user_translator():
        return _User(UserRole.TRANSLATOR)

    app.dependency_overrides[deps.current_user_dep] = _fake_current_user_translator

    client = TestClient(app)

    files = {"original_file": ("a.txt", b"hello", "text/plain")}
    data = {"language_code": "cs"}

    res = client.post("/projects", data=data, files=files, headers=_auth_header("x"))
    assert res.status_code == 403

    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_create_project_rejects_too_large(monkeypatch):
    """Chování limitu uploadu."""

    from app.api import deps
    from app.domain.enums import UserRole

    class _User:
        def __init__(self):
            self.id = uuid4()
            self.role = UserRole.CUSTOMER

    async def _fake_current_user_customer():
        return _User()

    app.dependency_overrides[deps.current_user_dep] = _fake_current_user_customer

    from app.core import config

    orig = config.settings.max_upload_mb
    config.settings.max_upload_mb = 1

    try:
        client = TestClient(app)
        too_big = b"x" * (1 * 1024 * 1024 + 1)

        files = {"original_file": ("a.bin", too_big, "application/octet-stream")}
        data = {"language_code": "cs"}

        res = client.post("/projects", data=data, files=files, headers=_auth_header("x"))
        assert res.status_code == 413
    finally:
        config.settings.max_upload_mb = orig
        app.dependency_overrides = {}
