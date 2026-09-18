import os
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

environment = os.environ["ENV"]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    environment: str


class ExampleResponse(BaseModel):
    status: Literal["ok"]
    service: Literal["FastAPI"]


app = FastAPI(
    title="HackSpain API",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)


@app.get("/api/health")
def health() -> HealthResponse:
    return HealthResponse(status="ok", environment=environment)


@app.get("/api/example")
def example() -> ExampleResponse:
    return ExampleResponse(status="ok", service="FastAPI")
