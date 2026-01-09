from __future__ import annotations

import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables.

    This project uses `pydantic-settings` so values can be provided via:
    - environment variables
    - a local `.env` file

    Attributes:
        mongodb_uri: MongoDB connection URI.
        mongodb_db: MongoDB database name.
        max_upload_mb: Maximum upload size in megabytes.
        jwt_secret: Secret key used to sign JWT tokens (override in env for production).
        jwt_algorithm: JWT signing algorithm.
        jwt_access_token_exp_minutes: Access token expiration time in minutes.
        smtp_host: SMTP host (mock server: MailHog in docker-compose).
        smtp_port: SMTP port.
        smtp_from: Default From email address.
        otp_master_secret: Global secret used for OTP-related derivations (override in env).
        otp_issuer: Issuer name used in otpauth provisioning URI.
        otp_interval_seconds: TOTP time step.
        otp_valid_window: Allowed time window for OTP verification.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # MongoDB
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "piae"

    # Uploads
    max_upload_mb: int = 5

    # JWT
    jwt_secret: str = os.environ.get("JWT_SECRET", "jwt-secret-for-dev-only")
    jwt_algorithm: str = "HS256"
    jwt_access_token_exp_minutes: int = 60

    # SMTP
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_from: str = "no-reply@piae.local"

    # OTP (TOTP) - second authentication method
    otp_master_secret: str = os.environ.get("OTP_MASTER_SECRET", "otp-master-secret-for-dev-only")
    otp_issuer: str = "PIAE"
    otp_interval_seconds: int = 30
    otp_valid_window: int = 1


settings = Settings()  # loads env/.env via pydantic-settings

if not settings.jwt_secret or not settings.otp_master_secret:
    raise RuntimeError("Missing required secrets: JWT_SECRET and/or OTP_MASTER_SECRET")
