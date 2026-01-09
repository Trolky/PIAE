from __future__ import annotations

import pytest

from app.api.auth import login
from app.security.passwords import hash_password


class _User:
    """Minimal user object used by auth login unit tests.

    This mimics the domain User model attributes accessed by the login endpoint.

    Args:
        user_id: UUID string.
        name: Username.
        role: Role name (e.g., "CUSTOMER").
        password_hash: Stored password hash.
    """

    def __init__(self, *, user_id: str, name: str, role: str, password_hash: str) -> None:
        from uuid import UUID

        from app.domain.enums import UserRole

        self.id = UUID(user_id)
        self.name = name
        self.role = UserRole(role)
        self.password_hash = password_hash


class _UserRepoFake:
    """Fake UserRepository providing only `get_by_name` for login tests."""

    def __init__(self, user: _User | None) -> None:
        self._user = user

    async def get_by_name(self, name: str):
        if self._user is None:
            return None
        if self._user.name == name:
            return self._user
        return None


@pytest.mark.asyncio
async def test_login_invalid_user(monkeypatch) -> None:
    """Login should fail with 401 when the user does not exist.

    Scenario:
        Repository returns no user for the provided username.

    Expected behavior:
        Endpoint raises an exception containing "Invalid credentials".
    """
    from app import api

    monkeypatch.setattr(api.auth, "UserRepository", lambda db: _UserRepoFake(None))

    payload = api.auth.LoginIn.model_validate({"username": "alice", "password": "x"})

    with pytest.raises(Exception) as exc:
        await login(payload=payload, db=None)
    assert "Invalid credentials" in str(exc.value)


@pytest.mark.asyncio
async def test_login_invalid_password(monkeypatch) -> None:
    """Login should fail with 401 when the password is incorrect.

    Scenario:
        Repository returns a user, but password verification fails.

    Expected behavior:
        Endpoint raises an exception containing "Invalid credentials".
    """
    from uuid import uuid4

    from app import api

    u = _User(user_id=str(uuid4()), name="alice", role="CUSTOMER", password_hash=hash_password("correct"))
    monkeypatch.setattr(api.auth, "UserRepository", lambda db: _UserRepoFake(u))

    payload = api.auth.LoginIn.model_validate({"username": "alice", "password": "wrong"})

    with pytest.raises(Exception) as exc:
        await login(payload=payload, db=None)
    assert "Invalid credentials" in str(exc.value)


@pytest.mark.asyncio
async def test_login_success(monkeypatch) -> None:
    """Login should return a JWT token for valid credentials.

    Scenario:
        Repository returns a user and password matches.

    Expected behavior:
        Response contains access_token, bearer token_type and correct user info.
    """
    from uuid import uuid4

    from app import api

    u = _User(user_id=str(uuid4()), name="alice", role="CUSTOMER", password_hash=hash_password("secret"))
    monkeypatch.setattr(api.auth, "UserRepository", lambda db: _UserRepoFake(u))

    payload = api.auth.LoginIn.model_validate({"username": "alice", "password": "secret"})

    res = await login(payload=payload, db=None)
    assert res.access_token
    assert res.token_type == "bearer"
    assert str(res.user_id) == str(u.id)
    assert res.role == "CUSTOMER"
