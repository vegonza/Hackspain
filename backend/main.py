import os
import logging
import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel
from documents.router import router as documents_router
from usage.router import router as usage_router
from suppliers.router import router as suppliers_router
from usage.worker import start_usage_worker
from shared.logger import setup_logger

environment = os.environ["ENV"]
logger = setup_logger()
logging.getLogger("httpx").setLevel(logging.WARNING)


class HealthResponse(BaseModel):
    status: Literal["ok"]
    environment: str


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    stop, thread = start_usage_worker()
    try:
        yield
    finally:
        stop.set()
        await asyncio.to_thread(thread.join, 5)


app = FastAPI(
    lifespan=lifespan,
    title="HackSpain API",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)
app.include_router(documents_router)
app.include_router(usage_router)
app.include_router(suppliers_router)


@app.get("/api/health")
def health() -> HealthResponse:
    return HealthResponse(status="ok", environment=environment)
