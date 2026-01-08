from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.feedback import router as feedback_router
from app.api.health import router as health_router
from app.api.projects import router as projects_router
from app.api.users import router as users_router
from app.db.mongo import ping_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan handler.

    Ensures MongoDB is reachable during application startup.

    Args:
        app: FastAPI application.

    Yields:
        None
    """

    await ping_db()
    yield


# FastAPI application instance.
app = FastAPI(title="PIAE", version="0.1.0", lifespan=lifespan)

# CORS origins (comma-separated) - useful for local dev, e.g. http://localhost:8001
_cors = os.environ.get("CORS_ALLOW_ORIGINS", "").strip()
if _cors:
    allow_origins = [o.strip() for o in _cors.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(projects_router)
app.include_router(feedback_router)
