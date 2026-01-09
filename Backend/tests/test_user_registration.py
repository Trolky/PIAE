from __future__ import annotations

import pytest

from app.api.users import RegisterUserIn, register_customer, register_translator


class _RepoFake:
    """In-memory fake for UserRepository used by registration unit tests."""

    def __init__(self, *, fail_on_create: bool = False) -> None:
        self.fail_on_create = fail_on_create
        self.created = []

    async def ensure_indexes(self) -> None:
        return None

    async def create(self, user):
        if self.fail_on_create:
            raise Exception("duplicate")
        self.created.append(user)


@pytest.mark.asyncio
async def test_register_customer_success(monkeypatch) -> None:
    """Registration should create a CUSTOMER account with a hashed password.

    Scenario:
        - Request payload is valid.
        - Repository create succeeds.

    Expected behavior:
        - Endpoint returns a user with CUSTOMER role.
        - Password is stored as a hash.
        - Repository create is called.
    """
    from app import api

    fake = _RepoFake()
    monkeypatch.setattr(api.users, "UserRepository", lambda db: fake)

    payload = RegisterUserIn.model_validate(
        {
            "name": "alice123",
            "email_address": "alice@example.com",
            "password": "secret1234",
        }
    )

    res = await register_customer(payload=payload, db=None)
    assert res.role.value == "CUSTOMER"
    assert res.name == "alice123"
    assert res.email_address == "alice@example.com"
    assert fake.created
    assert fake.created[0].role.value == "CUSTOMER"
    assert fake.created[0].password_hash


@pytest.mark.asyncio
async def test_register_translator_success(monkeypatch) -> None:
    """Registration should create a TRANSLATOR account.

    Scenario:
        - Request payload is valid.
        - Repository create succeeds.

    Expected behavior:
        - Endpoint returns a user with TRANSLATOR role.
        - Repository create is called.
    """
    from app import api

    fake = _RepoFake()
    monkeypatch.setattr(api.users, "UserRepository", lambda db: fake)

    payload = RegisterUserIn.model_validate(
        {
            "name": "bob123",
            "email_address": "bob@example.com",
            "password": "secret1234",
        }
    )

    res = await register_translator(payload=payload, db=None)
    assert res.role.value == "TRANSLATOR"
    assert fake.created
    assert fake.created[0].role.value == "TRANSLATOR"


@pytest.mark.asyncio
async def test_register_duplicate_returns_409(monkeypatch) -> None:
    """Registration should fail with a conflict when user already exists.

    Scenario:
        - Repository create fails (e.g., duplicate key).

    Expected behavior:
        - Endpoint raises an exception containing "already exists".
    """
    from app import api

    fake = _RepoFake(fail_on_create=True)
    monkeypatch.setattr(api.users, "UserRepository", lambda db: fake)

    payload = RegisterUserIn.model_validate(
        {
            "name": "alice123",
            "email_address": "alice@example.com",
            "password": "secret1234",
        }
    )

    with pytest.raises(Exception) as exc:
        await register_customer(payload=payload, db=None)

    assert "already exists" in str(exc.value)
