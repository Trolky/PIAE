from __future__ import annotations

import hashlib
import logging

from passlib.context import CryptContext

logger = logging.getLogger(__name__)

_pwd = CryptContext(schemes=["argon2"], deprecated="auto")


def _normalize_password(password: str) -> str:
    """Normalize password input used for key-derivation.

    For extremely large passwords we apply a deterministic pre-hash (SHA-256) to:
    - avoid potential DoS by forcing huge inputs into the KDF
    - keep input size reasonable and consistent

    Args:
        password: Raw plaintext password.

    Returns:
        str: Normalized password (either original or SHA-256 hex).
    """

    raw = password.encode("utf-8")
    if len(raw) <= 1024:
        return password
    return hashlib.sha256(raw).hexdigest()


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2.

    Args:
        password: Plaintext password.

    Returns:
        str: Argon2 hash string.
    """

    return _pwd.hash(_normalize_password(password))


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a stored hash.

    Args:
        password: Plaintext password.
        password_hash: Stored password hash.

    Returns:
        bool: True if valid.
    """

    try:
        return bool(_pwd.verify(_normalize_password(password), password_hash))
    except Exception as ex:
        logger.warning("Password verify failed", exc_info=ex)
        return False


def needs_rehash(password_hash: str) -> bool:
    """Check whether a stored hash should be re-hashed.

    This becomes relevant if Argon2 parameters change over time.

    Args:
        password_hash: Stored password hash.

    Returns:
        bool: True if the hash should be updated.
    """

    try:
        return bool(_pwd.needs_update(password_hash))
    except Exception:
        return False
