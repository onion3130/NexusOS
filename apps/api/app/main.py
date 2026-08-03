"""NexusOS API application entrypoint for Milestone 5."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes.assistant import approval_router as assistant_approval_router
from app.api.routes.assistant import router as assistant_router
from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.system import router as system_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.notes import router as notes_router
from app.api.routes.host_actions import router as host_actions_router
from app.api.routes.workspace_views import router as workspace_views_router
from app.core.config import cors_origins_from_environment, get_settings


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Validate configuration before accepting requests; never auto-migrate."""
    get_settings()
    yield


app = FastAPI(
    title="NexusOS API",
    version=__version__,
    description="NexusOS identity, persistence, read-only system, and bounded assistant API.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins_from_environment(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "Idempotency-Key"],
)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(assistant_router)
app.include_router(assistant_approval_router)
app.include_router(system_router)
app.include_router(tasks_router)
app.include_router(notes_router)
app.include_router(host_actions_router)
app.include_router(workspace_views_router)
