"""NexusOS API application entrypoint for Milestone 1."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from app import __version__
from app.api.routes.health import router as health_router
from app.core.config import get_settings


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Validate configuration before accepting requests."""
    get_settings()
    yield


app = FastAPI(
    title="NexusOS API",
    version=__version__,
    description="NexusOS Milestone 1 foundation API.",
    lifespan=lifespan,
)
app.include_router(health_router)
