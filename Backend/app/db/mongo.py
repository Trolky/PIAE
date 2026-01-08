from __future__ import annotations

import logging
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings

logger = logging.getLogger(__name__)


_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None


def get_client() -> AsyncIOMotorClient:
    """Return a singleton MongoDB client.

    Returns:
        AsyncIOMotorClient: MongoDB client.
    """
    global _client
    if _client is None:
        logger.info("Connecting to MongoDB", extra={"mongodb_uri": settings.mongodb_uri})
        _client = AsyncIOMotorClient(settings.mongodb_uri)
    return _client


def get_db() -> AsyncIOMotorDatabase:
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
    db = get_db()
    res = await db.command("ping")
    ok = bool(res.get("ok"))
    logger.info("MongoDB ping", extra={"ok": ok, "db": settings.mongodb_db})
    return ok
