from __future__ import annotations

import logging
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field

from app.api.deps import CurrentUser, Db
from app.domain.enums import UserRole
from app.domain.models import TranslatorLanguage, User
from app.repositories.translator_languages import TranslatorLanguageRepository
from app.repositories.users import UserRepository

logger = logging.getLogger(__name__)

router: APIRouter = APIRouter(prefix="/users", tags=["users"])


class RegisterUserIn(BaseModel):
    """Request body for user registration.

    Attributes:
        name: Alphanumeric username.
        email_address: User email.
        password: Plaintext password (hashed server-side).
    """

    name: str = Field(pattern=r"^[A-Za-z0-9]+$", description="Alfanumerický username")
    email_address: EmailStr

    password: str = Field(min_length=8, description="Plaintext password (will be hashed on server)")


class RegisterUserOut(BaseModel):
    """Response model returned after registration."""

    id: UUID
    name: str
    email_address: EmailStr
    role: UserRole


class AddTranslatorLanguageIn(BaseModel):
    """Request body for adding a translator language."""

    language_code: str = Field(min_length=2, max_length=2, description="ISO 639-1")


class TranslatorLanguageOut(BaseModel):
    """Response model returned after adding a translator language."""

    translator_id: UUID
    language_code: str


class TranslatorLanguagesOut(BaseModel):
    """Response model listing translator languages."""

    translator_id: UUID
    languages: list[str]


@router.post("/customers/register", response_model=RegisterUserOut, status_code=201)
async def register_customer(payload: RegisterUserIn, db: Db) -> RegisterUserOut:
    """Register a new customer account.

    Args:
        payload: Registration payload.
        db: MongoDB database dependency.

    Returns:
        RegisterUserOut: Created user info.

    Raises:
        HTTPException: If user already exists.
    """
    repo: UserRepository = UserRepository(db)
    await repo.ensure_indexes()

    from app.security.passwords import hash_password

    user: User = User(
        id=uuid4(),
        name=payload.name,
        email_address=payload.email_address,
        role=UserRole.CUSTOMER,
        password_hash=hash_password(payload.password),
    )

    try:
        await repo.create(user)
    except Exception as ex:
        logger.warning("Failed to create customer", exc_info=ex)
        raise HTTPException(status_code=409, detail="User with this email or name already exists")

    return RegisterUserOut(id=user.id, name=user.name, email_address=user.email_address, role=user.role)


@router.post("/translators/register", response_model=RegisterUserOut, status_code=201)
async def register_translator(payload: RegisterUserIn, db: Db) -> RegisterUserOut:
    """Register a new translator account."""
    repo: UserRepository = UserRepository(db)
    await repo.ensure_indexes()

    from app.security.passwords import hash_password

    user: User = User(
        id=uuid4(),
        name=payload.name,
        email_address=payload.email_address,
        role=UserRole.TRANSLATOR,
        password_hash=hash_password(payload.password),
    )

    try:
        await repo.create(user)
    except Exception as ex:
        logger.warning("Failed to create translator", exc_info=ex)
        raise HTTPException(status_code=409, detail="User with this email or name already exists")

    return RegisterUserOut(id=user.id, name=user.name, email_address=user.email_address, role=user.role)


@router.get("/{user_id}", response_model=RegisterUserOut)
async def get_user(user_id: UUID, db: Db) -> RegisterUserOut:
    """Get a user by id.

    Args:
        user_id: User UUID.
        db: MongoDB database dependency.

    Returns:
        RegisterUserOut: User info.

    Raises:
        HTTPException: If not found.
    """
    repo: UserRepository = UserRepository(db)
    user: User | None = await repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    return RegisterUserOut(id=user.id, name=user.name, email_address=user.email_address, role=user.role)


def _assert_language_access(*, current_user: User, translator_id: UUID) -> None:
    """Authorize access to translator language management.

    Args:
        current_user: Authenticated user.
        translator_id: Translator UUID.

    Raises:
        HTTPException: If access is denied.
    """
    if current_user.role == UserRole.ADMINISTRATOR:
        return
    if current_user.role == UserRole.TRANSLATOR and current_user.id == translator_id:
        return
    raise HTTPException(status_code=403, detail="Not allowed")


@router.get("/translators/{translator_id}/languages", response_model=TranslatorLanguagesOut)
async def list_translator_languages(
    translator_id: UUID,
    db: Db,
    current_user: CurrentUser,
) -> TranslatorLanguagesOut:
    """List languages configured for a translator.

    Access:
        - ADMINISTRATOR: any translator
        - TRANSLATOR: only own languages

    Args:
        translator_id: Translator UUID.
        db: MongoDB database dependency.
        current_user: Authenticated user.

    Returns:
        TranslatorLanguagesOut: Language codes.
    """
    _assert_language_access(current_user=current_user, translator_id=translator_id)

    users: UserRepository = UserRepository(db)
    translator: User | None = await users.get_by_id(translator_id)
    if translator is None or translator.role != UserRole.TRANSLATOR:
        raise HTTPException(status_code=404, detail="Translator not found")

    tl_repo: TranslatorLanguageRepository = TranslatorLanguageRepository(db)
    await tl_repo.ensure_indexes()

    langs: list[str] = await tl_repo.list_languages_for_translator(str(translator_id))
    langs_sorted: list[str] = sorted({l.lower() for l in langs})
    return TranslatorLanguagesOut(translator_id=translator_id, languages=langs_sorted)


@router.post("/translators/{translator_id}/languages", response_model=TranslatorLanguageOut, status_code=201)
async def add_translator_language(
    translator_id: UUID,
    payload: AddTranslatorLanguageIn,
    db: Db,
    current_user: CurrentUser,
) -> TranslatorLanguageOut:
    """Add a language for a translator."""
    _assert_language_access(current_user=current_user, translator_id=translator_id)

    users: UserRepository = UserRepository(db)
    translator: User | None = await users.get_by_id(translator_id)
    if translator is None or translator.role != UserRole.TRANSLATOR:
        raise HTTPException(status_code=404, detail="Translator not found")

    tl_repo: TranslatorLanguageRepository = TranslatorLanguageRepository(db)
    await tl_repo.ensure_indexes()

    tl: TranslatorLanguage = TranslatorLanguage(translator_id=translator_id, language_code=payload.language_code.lower())
    await tl_repo.add_language(tl)

    return TranslatorLanguageOut(translator_id=translator_id, language_code=tl.language_code)


@router.delete("/translators/{translator_id}/languages/{language_code}", status_code=204)
async def delete_translator_language(
    translator_id: UUID,
    language_code: str,
    db: Db,
    current_user: CurrentUser,
) -> None:
    """Remove a language from a translator."""
    _assert_language_access(current_user=current_user, translator_id=translator_id)

    users: UserRepository = UserRepository(db)
    translator: User | None = await users.get_by_id(translator_id)
    if translator is None or translator.role != UserRole.TRANSLATOR:
        raise HTTPException(status_code=404, detail="Translator not found")

    if len(language_code) != 2:
        raise HTTPException(status_code=422, detail="Invalid language code")

    tl_repo: TranslatorLanguageRepository = TranslatorLanguageRepository(db)
    await tl_repo.ensure_indexes()
    await tl_repo.delete_language(translator_id=str(translator_id), language_code=language_code.lower())

    return None
