from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, EmailStr, Field

from app.domain.enums import ProjectState, UserRole


def utc_now() -> datetime:
    """Return current UTC datetime.

    Returns:
        datetime: Timezone-aware datetime in UTC.
    """
    return datetime.now(timezone.utc)


class User(BaseModel):
    """Application user.

    Attributes:
        id: User UUID.
        name: Unique alphanumeric username.
        email_address: Unique email address.
        role: User role (CUSTOMER/TRANSLATOR/ADMINISTRATOR).
        password_hash: Password hash stored server-side (argon2).
        otp_enabled: Whether OTP (TOTP) is enabled for the user.
        otp_secret: Base32 secret for OTP, stored per-user.
    """

    id: UUID
    name: str
    email_address: EmailStr
    role: UserRole

    password_hash: str = Field(min_length=1, description="Hash hesla.")

    # OTP (TOTP) druhá metoda přihlášení
    otp_enabled: bool = False
    otp_secret: Optional[str] = Field(
        default=None,
        description="Base32 secret pro TOTP (uložený per-user).",
    )


class TranslatorLanguage(BaseModel):
    """Mapping between a translator and a target language.

    Attributes:
        translator_id: Translator user UUID.
        language_code: ISO 639-1 code (two letters).
    """

    translator_id: UUID
    language_code: str = Field(min_length=2, max_length=2, description="ISO 639-1")


class Feedback(BaseModel):
    """Customer feedback associated with a project (1:1).

    Attributes:
        id: Feedback UUID.
        project_id: Project UUID.
        text: Feedback text (may be empty for APPROVED).
        created_at: UTC timestamp.
    """

    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    text: str
    created_at: datetime = Field(default_factory=utc_now)


class Project(BaseModel):
    """Translation project.

    Attributes:
        id: Project UUID.
        customer_id: Customer UUID.
        translator_id: Translator UUID (nullable until assigned).
        language_code: Target language (ISO 639-1).
        original_file_id: GridFS ObjectId (string) for the original uploaded file.
        translated_file_id: GridFS ObjectId (string) for the translated file (nullable).
        state: Project state machine value.
        created_at: UTC timestamp.
        feedback_id: Reference to Feedback collection (nullable).
    """

    id: UUID
    customer_id: UUID
    translator_id: Optional[UUID] = None
    language_code: str = Field(min_length=2, max_length=2, description="ISO 639-1")

    # GridFS ObjectId jako string
    original_file_id: str
    translated_file_id: Optional[str] = None

    state: ProjectState = ProjectState.CREATED
    created_at: datetime = Field(default_factory=utc_now)

    # reference na Feedback kolekci
    feedback_id: Optional[UUID] = None
