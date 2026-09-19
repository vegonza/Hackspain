from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel
from shared.storage import get_client
from shared.redis import get_redis
from shared.retries import RetryState
from documents.queue import RETRIES


class Document(BaseModel):
    id: UUID
    name: str
    sha256: str
    created_at: datetime
    status: Literal["queued", "processing", "ready", "error"] = "queued"
    pages: int = 0
    retry_attempts: int = 0
    last_error: str | None = None
    next_retry_at: datetime | None = None


def with_retry_state(document: Document, state: RetryState) -> Document:
    document.retry_attempts = state.attempts
    document.last_error = state.last_error
    document.next_retry_at = datetime.fromtimestamp(state.next_attempt, timezone.utc) if state.next_attempt is not None else None
    if document.status != "ready":
        if state.failed:
            document.status = "error"
        elif state.next_attempt is not None:
            document.status = "queued"
    return document


def read_document(document_id: UUID) -> Document:
    rows = get_client().table("documents").select("*").eq("id", str(document_id)).is_("deleted_at", "null").execute().data
    if not rows:
        raise HTTPException(status_code=404, detail="document_not_found")
    with get_redis() as redis:
        payload = redis.hget(RETRIES, str(document_id))
    return with_retry_state(Document.model_validate(rows[0]), RetryState.model_validate_json(payload) if payload is not None else RetryState())


def list_documents() -> list[Document]:
    documents: list[Document] = []
    while True:
        rows = get_client().table("documents").select("*").is_("deleted_at", "null").order("created_at", desc=True).order("id").range(len(documents), len(documents) + 999).execute().data
        if rows:
            with get_redis() as redis:
                states = redis.hmget(RETRIES, [row["id"] for row in rows])
            documents.extend(with_retry_state(Document.model_validate(row), RetryState.model_validate_json(state) if state is not None else RetryState()) for row, state in zip(rows, states))
        if len(rows) < 1000:
            return documents


def find_document_by_hash(sha256: str) -> bool:
    return bool(get_client().table("documents").select("id").eq("sha256", sha256).is_("deleted_at", "null").limit(1).execute().data)


def create_document(document: Document) -> None:
    get_client().table("documents").insert(document.model_dump(mode="json", exclude={"retry_attempts", "last_error", "next_retry_at"})).execute()


def write_document(document: Document) -> None:
    get_client().table("documents").upsert(document.model_dump(mode="json", exclude={"retry_attempts", "last_error", "next_retry_at"})).execute()


def archive_document(document_id: UUID) -> None:
    get_client().table("documents").update({"deleted_at": datetime.now(timezone.utc).isoformat()}).eq("id", str(document_id)).execute()
