from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.domain.models import TranslatorLanguage


class TranslatorLanguageRepository:
    """MongoDB repository for translator language capabilities.

    Collection: `translator_languages`.

    The repository stores (translator_id, language_code) pairs. A unique compound
    index enforces that the same language cannot be added twice for the same
    translator.

    Args:
        db: Motor database handle.
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        """Initialize the repository.

        Args:
            db: Motor database handle.
        """
        self._col = db["translator_languages"]

    async def ensure_indexes(self) -> None:
        """Create MongoDB indexes required by the application."""
        await self._col.create_index([("translator_id", 1), ("language_code", 1)], unique=True)
        await self._col.create_index("language_code")

    async def list_translator_ids_for_language(self, language_code: str) -> list[str]:
        """List translator ids configured for a given language.

        Args:
            language_code: ISO 639-1 code.

        Returns:
            list[str]: Translator ids as strings.
        """
        cursor = self._col.find({"language_code": language_code}, projection={"translator_id": 1})
        docs = await cursor.to_list(length=10000)
        return [d["translator_id"] for d in docs]

    async def list_languages_for_translator(self, translator_id: str) -> list[str]:
        """List language codes configured for a translator.

        Args:
            translator_id: Translator UUID as string.

        Returns:
            list[str]: Language codes.
        """
        cursor = self._col.find({"translator_id": translator_id}, projection={"language_code": 1})
        docs = await cursor.to_list(length=10000)
        return [d["language_code"] for d in docs]

    async def add_language(self, tl: TranslatorLanguage) -> None:
        """Add a translator language if it does not exist (idempotent).

        Args:
            tl: TranslatorLanguage model.
        """
        await self._col.update_one(
            {"translator_id": str(tl.translator_id), "language_code": tl.language_code},
            {"$setOnInsert": tl.model_dump(mode="json")},
            upsert=True,
        )

    async def delete_language(self, *, translator_id: str, language_code: str) -> None:
        """Remove a translator language.

        Args:
            translator_id: Translator UUID as string.
            language_code: ISO 639-1 code.
        """
        await self._col.delete_one({"translator_id": translator_id, "language_code": language_code})
