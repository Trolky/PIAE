from __future__ import annotations

import pyotp
from fastapi.testclient import TestClient

from app.main import app


def test_otp_login_happy_path(monkeypatch):
    class _Role:
        value = "CUSTOMER"

    class _User:
        def __init__(self):
            self.id = "00000000-0000-0000-0000-000000000000"
            self.name = "alice"
            self.role = _Role()
            self.password_hash = "x"
            self.otp_enabled = True
            self.otp_secret = "JBSWY3DPEHPK3PXP"  # base32

    async def _get_by_name(self, name: str):
        return _User() if name == "alice" else None

    from app.repositories.users import UserRepository

    monkeypatch.setattr(UserRepository, "get_by_name", _get_by_name, raising=True)

    client = TestClient(app)

    otp = pyotp.TOTP("JBSWY3DPEHPK3PXP", interval=30).now()
    resp = client.post("/auth/otp/login", json={"username": "alice", "otp": otp})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["role"] == "CUSTOMER"


def test_otp_login_requires_enabled(monkeypatch):
    class _Role:
        value = "CUSTOMER"

    class _User:
        def __init__(self):
            self.id = "00000000-0000-0000-0000-000000000000"
            self.name = "alice"
            self.role = _Role()
            self.password_hash = "x"
            self.otp_enabled = False
            self.otp_secret = None

    async def _get_by_name(self, name: str):
        return _User() if name == "alice" else None

    from app.repositories.users import UserRepository

    monkeypatch.setattr(UserRepository, "get_by_name", _get_by_name, raising=True)

    client = TestClient(app)

    otp = pyotp.TOTP("JBSWY3DPEHPK3PXP", interval=30).now()
    resp = client.post("/auth/otp/login", json={"username": "alice", "otp": otp})
    assert resp.status_code == 401


def test_otp_login_invalid_code(monkeypatch):
    class _Role:
        value = "CUSTOMER"

    class _User:
        def __init__(self):
            self.id = "00000000-0000-0000-0000-000000000000"
            self.name = "alice"
            self.role = _Role()
            self.password_hash = "x"
            self.otp_enabled = True
            self.otp_secret = "JBSWY3DPEHPK3PXP"

    async def _get_by_name(self, name: str):
        return _User() if name == "alice" else None

    from app.repositories.users import UserRepository

    monkeypatch.setattr(UserRepository, "get_by_name", _get_by_name, raising=True)

    client = TestClient(app)

    resp = client.post("/auth/otp/login", json={"username": "alice", "otp": "000000"})
    assert resp.status_code == 401
