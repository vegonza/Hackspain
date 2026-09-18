from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from fastapi import HTTPException
from pydantic import BaseModel

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class Document(BaseModel):
    id: UUID
    name: str
    created_at: datetime
    status: Literal["queued", "processing", "ready", "error"] = "queued"
    pages: int = 0


def document_directory(document_id: UUID) -> Path:
    directory = DATA_DIR / str(document_id)
    if not (directory / "metadata.json").is_file():
        raise HTTPException(status_code=404, detail="document_not_found")
    return directory


def read_document(directory: Path) -> Document:
    return Document.model_validate_json((directory / "metadata.json").read_text())


def write_document(directory: Path, document: Document) -> None:
    temporary = directory / f"metadata-{uuid4()}.tmp"
    temporary.write_text(document.model_dump_json(), encoding="utf-8")
    temporary.replace(directory / "metadata.json")
