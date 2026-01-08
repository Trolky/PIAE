from __future__ import annotations

import logging

import pyotp

from app.core.config import settings

logger = logging.getLogger(__name__)


def generate_secret() -> str:
    """Generate a new base32 secret for TOTP.

    Returns:
        str: Random base32 secret.
    """
    return pyotp.random_base32()


def totp_from_secret(secret: str) -> pyotp.TOTP:
    """Create a TOTP instance from a base32 secret.

    Args:
        secret: Base32 secret.

    Returns:
        pyotp.TOTP: Configured TOTP generator.
    """
    return pyotp.TOTP(secret, interval=settings.otp_interval_seconds)


def verify_totp_secret(*, secret: str, code: str) -> bool:
    """Verify a TOTP code for a given secret.

    Args:
        secret: Base32 secret.
        code: TOTP code as entered by user.

    Returns:
        bool: True if the code is valid within the configured time window.
    """
    code = (code or "").strip().replace(" ", "")
    if not code.isdigit():
        return False

    totp = totp_from_secret(secret)
    ok = totp.verify(code, valid_window=settings.otp_valid_window)
    logger.info("TOTP verify", extra={"ok": ok})
    return bool(ok)


def provisioning_uri_from_secret(*, secret: str, username: str) -> str:
    """Generate an otpauth provisioning URI for authenticator apps.

    Args:
        secret: Base32 secret.
        username: Username shown in authenticator.

    Returns:
        str: otpauth URI.
    """
    totp = totp_from_secret(secret)
    return totp.provisioning_uri(name=username, issuer_name=settings.otp_issuer)
