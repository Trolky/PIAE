from __future__ import annotations

import logging
from typing import Any, Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings

logger = logging.getLogger(__name__)


_client: Optional[AsyncIOMotorClient[Any]] = None
_db: Optional[AsyncIOMotorDatabase[Any]] = None


def get_client() -> AsyncIOMotorClient[Any]:
    """Return a singleton MongoDB client.

    Returns:
        AsyncIOMotorClient: MongoDB client.
    """
    global _client
    if _client is None:
        logger.info("Connecting to MongoDB", extra={"mongodb_uri": settings.mongodb_uri})
        _client = AsyncIOMotorClient(settings.mongodb_uri)
    return _client


def get_db() -> AsyncIOMotorDatabase[Any]:
    """Return a singleton database handle.

    Returns:
        AsyncIOMotorDatabase: Database for current configuration.
    """
    global _db
    if _db is None:
        _db = get_client()[settings.mongodb_db]
    return _db


async def ping_db() -> bool:
    """Ping MongoDB to verify connectivity.

    Returns:
        bool: True if ping succeeded.

    Raises:
        Any: Propagates underlying Motor errors to fail application startup.
    """
    db: AsyncIOMotorDatabase[Any] = get_db()
    res: dict[str, Any] = await db.command("ping")
    ok: bool = bool(res.get("ok"))
    logger.info("MongoDB ping", extra={"ok": ok, "db": settings.mongodb_db})
    return ok
