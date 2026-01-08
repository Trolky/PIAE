from __future__ import annotations

from fastapi import APIRouter

from app.db.mongo import ping_db

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health() -> dict[str, str]:
    """Health check endpoint.

    Performs a MongoDB ping.

    Returns:
        dict[str, str]: {"status": "ok"|"fail"}
    """
    ok = await ping_db()
    return {"status": "ok" if ok else "fail"}
