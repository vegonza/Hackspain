import os
import logging
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel
from documents.router import router as documents_router
from usage.router import router as usage_router
from shared.logger import setup_logger

environment = os.environ["ENV"]
logger = setup_logger()
logging.getLogger("httpx").setLevel(logging.WARNING)


class HealthResponse(BaseModel):
    status: Literal["ok"]
    environment: str


app = FastAPI(
    title="HackSpain API",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)
app.include_router(documents_router)
app.include_router(usage_router)


@app.get("/api/health")
def health() -> HealthResponse:
    return HealthResponse(status="ok", environment=environment)
