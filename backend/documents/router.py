from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from documents.processor import extract_markdown
from documents.features import InvoiceFeatures, extract_invoice_features
from shared.logger import get_logger

logger = get_logger()
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
router = APIRouter(prefix="/api/documents")


class Document(BaseModel):
    id: UUID
    name: str
    created_at: datetime
    status: Literal["ready", "error"] = "error"
    pages: int = 0


class DocumentDetail(Document):
    markdown: str
    features: InvoiceFeatures | None


def document_directory(document_id: UUID) -> Path:
    directory = DATA_DIR / str(document_id)
    if not (directory / "metadata.json").is_file():
        raise HTTPException(status_code=404, detail="document_not_found")
    return directory


def read_document(directory: Path) -> Document:
    return Document.model_validate_json((directory / "metadata.json").read_text())


def write_document(directory: Path, document: Document) -> None:
    temporary = directory / "metadata.tmp"
    temporary.write_text(document.model_dump_json(), encoding="utf-8")
    temporary.replace(directory / "metadata.json")


def document_detail(directory: Path) -> DocumentDetail:
    document = read_document(directory)
    markdown = (directory / "document.md").read_text(encoding="utf-8") if document.status == "ready" else ""
    features = extract_invoice_features(markdown) if document.status == "ready" else None
    return DocumentDetail(**document.model_dump(), markdown=markdown, features=features)


@router.get("")
def list_documents() -> list[Document]:
    documents = [read_document(path.parent) for path in DATA_DIR.glob("*/metadata.json")]
    return sorted(documents, key=lambda document: document.created_at, reverse=True)


@router.post("", status_code=201)
def upload_document(file: UploadFile) -> DocumentDetail:
    name = file.filename
    pdf_bytes = file.file.read()
    if not name or not name.lower().endswith(".pdf") or not pdf_bytes.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="invalid_pdf")

    document = Document(id=uuid4(), name=name, created_at=datetime.now(timezone.utc))
    directory = DATA_DIR / str(document.id)
    directory.mkdir(parents=True)
    (directory / "original.pdf").write_bytes(pdf_bytes)
    write_document(directory, document)
    logger.info("[DOCUMENTS] Saved PDF %s (%s)", name, document.id)

    try:
        markdown, pages = extract_markdown(pdf_bytes, directory)
    except Exception:
        logger.exception("[DOCUMENTS] OCR failed for %s", name)
        raise HTTPException(status_code=502, detail="ocr_failed") from None

    (directory / "document.md").write_text(markdown, encoding="utf-8")
    document.status = "ready"
    document.pages = pages
    write_document(directory, document)
    logger.info("[DOCUMENTS] Markdown saved for %s (%s pages)", name, pages)
    return DocumentDetail(
        **document.model_dump(),
        markdown=markdown,
        features=extract_invoice_features(markdown),
    )


@router.get("/{document_id}")
def get_document(document_id: UUID) -> DocumentDetail:
    return document_detail(document_directory(document_id))


@router.delete("/{document_id}")
def delete_document(document_id: UUID) -> dict[str, bool]:
    directory = document_directory(document_id)
    document = read_document(directory)
    trash_directory = DATA_DIR / ".trash"
    try:
        trash_directory.mkdir(exist_ok=True)
        directory.rename(trash_directory / str(document_id))
    except OSError:
        logger.exception("[DOCUMENTS] Could not move %s to trash", document.name)
        raise HTTPException(status_code=500, detail="delete_failed") from None
    logger.info("[DOCUMENTS] Moved %s to trash (%s)", document.name, document_id)
    return {"deleted": True}


@router.get("/{document_id}/pdf")
def get_pdf(document_id: UUID) -> FileResponse:
    directory = document_directory(document_id)
    return FileResponse(directory / "original.pdf", media_type="application/pdf")


@router.get("/{document_id}/images/{filename}")
def get_image(document_id: UUID, filename: str) -> FileResponse:
    directory = document_directory(document_id)
    if not filename.startswith("page-") or not filename.endswith(".jpg") or Path(filename).name != filename:
        raise HTTPException(status_code=404, detail="image_not_found")
    path = directory / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="image_not_found")
    return FileResponse(path, media_type="image/jpeg")
