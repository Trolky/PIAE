from __future__ import annotations

"""Create three development users: administrator, customer, translator.

This script connects to the configured MongoDB database and ensures the users
exist. It is intended for local development only and will overwrite existing
users with the same id if present.

Usage:
    python Backend\scripts\create_dev_users.py
"""

import argparse
import asyncio
import logging
import os
from uuid import UUID


def _preconfigure_env() -> str:
    """Parse CLI args (if any) and ensure MONGODB_URI env var is set before
    importing application modules. Defaults to host.docker.internal for Docker
    setups when no value is provided.

    Returns:
        str: Final MongoDB URI used.
    """

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--mongodb-uri", dest="mongodb_uri", help="MongoDB URI to use (overrides env)")
    args, _ = parser.parse_known_args()

    if args.mongodb_uri:
        os.environ.setdefault("MONGODB_URI", args.mongodb_uri)
    # If no env var is set at all, default to Docker host mapping recommended
    # for containers connecting back to host services.
    if "MONGODB_URI" not in os.environ:
        os.environ["MONGODB_URI"] = "mongodb://host.docker.internal:27017"

    return os.environ["MONGODB_URI"]


# Ensure env is configured before importing Pydantic settings / app modules
_preconfigure_env()

from app.db.mongo import get_db
from app.domain.enums import UserRole
from app.domain.models import User
from app.repositories.users import UserRepository
from app.security.passwords import hash_password

logger = logging.getLogger(__name__)


async def _create_users() -> None:
    db = get_db()
    repo = UserRepository(db)

    await repo.ensure_indexes()

    users: list[User] = [
        User.model_validate(
            {
                "id": UUID("00000000-0000-0000-0000-000000000001"),
                "name": "admin",
                "email_address": "admin@example.com",
                "role": UserRole.ADMINISTRATOR,
                "password_hash": hash_password("adminpass"),
            }
        ),
        User.model_validate(
            {
                "id": UUID("00000000-0000-0000-0000-000000000002"),
                "name": "customer",
                "email_address": "customer@example.com",
                "role": UserRole.CUSTOMER,
                "password_hash": hash_password("customerpass"),
            }
        ),
        User.model_validate(
            {
                "id": UUID("00000000-0000-0000-0000-000000000003"),
                "name": "translator",
                "email_address": "translator@example.com",
                "role": UserRole.TRANSLATOR,
                "password_hash": hash_password("translatorpass"),
            }
        ),
    ]

    for u in users:
        await repo._col.update_one(
            {"id": str(u.id)},
            {"$set": u.model_dump(mode="json")},
            upsert=True,
        )
        logger.info("Created/updated user %s (%s)", u.name, u.role.value)


def main() -> None:
    """Run the creation routine in the event loop."""

    logging.basicConfig(level=logging.INFO)
    asyncio.run(_create_users())


if __name__ == "__main__":
    main()
