from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel
from shared.storage import get_client


class Document(BaseModel):
    id: UUID
    name: str
    created_at: datetime
    status: Literal["queued", "processing", "ready", "error"] = "queued"
    pages: int = 0


def read_document(document_id: UUID) -> Document:
    rows = get_client().table("documents").select("*").eq("id", str(document_id)).is_("deleted_at", "null").execute().data
    if not rows:
        raise HTTPException(status_code=404, detail="document_not_found")
    return Document.model_validate(rows[0])


def list_documents() -> list[Document]:
    documents: list[Document] = []
    while True:
        rows = get_client().table("documents").select("*").is_("deleted_at", "null").order("created_at", desc=True).order("id").range(len(documents), len(documents) + 999).execute().data
        documents.extend(Document.model_validate(row) for row in rows)
        if len(rows) < 1000:
            return documents


def write_document(document: Document) -> None:
    get_client().table("documents").upsert(document.model_dump(mode="json")).execute()


def archive_document(document_id: UUID) -> None:
    get_client().table("documents").update({"deleted_at": datetime.now(timezone.utc).isoformat()}).eq("id", str(document_id)).execute()
