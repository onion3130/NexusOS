"""NexusOS API application entrypoint for Milestone 2."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.core.config import cors_origins_from_environment, get_settings


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Validate configuration before accepting requests; never auto-migrate."""
    get_settings()
    yield


app = FastAPI(
    title="NexusOS API",
    version=__version__,
    description="NexusOS Milestone 2 identity and persistence API.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins_from_environment(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
)
app.include_router(health_router)
app.include_router(auth_router)
