from __future__ import annotations

import logging
from typing import Any, Optional, Tuple

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorGridFSBucket

logger = logging.getLogger(__name__)


class GridFsService:
    """Thin wrapper around MongoDB GridFS (Motor).

    Args:
        db: Motor database handle.
        bucket_name: GridFS bucket name (default: "files").
    """

    def __init__(self, db: AsyncIOMotorDatabase, *, bucket_name: str = "files") -> None:
        """Initialize the GridFS wrapper."""
        self._bucket: AsyncIOMotorGridFSBucket = AsyncIOMotorGridFSBucket(db, bucket_name=bucket_name)

    async def upload(
        self,
        *,
        filename: str,
        data: bytes,
        metadata: Optional[dict[str, Any]] = None,
    ) -> ObjectId:
        """Upload a file to GridFS.

        Args:
            filename: Stored filename.
            data: File bytes.
            metadata: Optional metadata (e.g., content_type).

        Returns:
            ObjectId: GridFS file id.
        """
        file_id = await self._bucket.upload_from_stream(filename, data, metadata=metadata or {})
        logger.info("GridFS upload", extra={"file_id": str(file_id), "stored_filename": filename})
        return file_id

    async def download(self, file_id: ObjectId) -> Tuple[bytes, dict[str, Any]]:
        """Download a file from GridFS.

        Args:
            file_id: GridFS ObjectId.

        Returns:
            tuple[bytes, dict[str, Any]]: (content, info) where info contains filename/length/metadata.
        """
        stream = await self._bucket.open_download_stream(file_id)
        assert stream is not None
        raw = await stream.read()
        content = bytes(raw)
        info: dict[str, Any] = {
            "filename": getattr(stream, "filename", None),
            "length": getattr(stream, "length", None),
            "metadata": getattr(stream, "metadata", None) or {},
        }
        return content, info

    async def delete(self, file_id: ObjectId) -> None:
        """Delete a file from GridFS.

        Args:
            file_id: GridFS ObjectId.
        """
        await self._bucket.delete(file_id)
        logger.info("GridFS delete", extra={"file_id": str(file_id)})
