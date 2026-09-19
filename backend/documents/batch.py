import hashlib
import re
from pathlib import Path

from pydantic import BaseModel

from pipeline.text_1 import extract_text
from pipeline.extraction_4.extraction import InvoiceExtraction
from shared.logger import get_logger

logger = get_logger()
ORDER_LABEL = re.compile(r"(?:\bpedido(?:\s+(?:asociado|cliente))?|\bPO)\s*:\s*(PO-\d{4}-\d+)", re.IGNORECASE)


class OrderReferences(BaseModel):
    sha256: str
    features_sha256: str
    orders: list[str]
    native_text_available: bool


class BatchIndex(BaseModel):
    documents: dict[str, OrderReferences]

    def other_documents(self, order: str, current: str) -> list[str]:
        return sorted(name for name, record in self.documents.items() if name != current and order in record.orders)


def refresh_order_index(source: Path, index_path: Path, extracted: Path) -> BatchIndex:
    index = BatchIndex.model_validate_json(index_path.read_text()) if index_path.exists() else BatchIndex(documents={})
    files = sorted(source.glob("*.pdf"))
    names = {path.name for path in files}
    for removed in index.documents.keys() - names:
        del index.documents[removed]
    changed = 0
    for path in files:
        pdf_bytes = path.read_bytes()
        digest = hashlib.sha256(pdf_bytes).hexdigest()
        extraction_path = extracted / path.stem / "features.json"
        extraction_digest = hashlib.sha256(extraction_path.read_bytes()).hexdigest() if extraction_path.exists() else ""
        if path.name not in index.documents or index.documents[path.name].sha256 != digest or index.documents[path.name].features_sha256 != extraction_digest:
            text = extract_text(pdf_bytes)
            index.documents[path.name] = OrderReferences(
                sha256=digest,
                features_sha256=extraction_digest,
                orders=sorted({match.upper() for match in ORDER_LABEL.findall(text)}),
                native_text_available=bool(text.strip()),
            )
            changed += 1
        if extraction_path.exists():
            extraction = InvoiceExtraction.model_validate_json(extraction_path.read_text())
            if extraction.purchase_order:
                record = index.documents[path.name]
                record.orders = sorted(set(record.orders) | {extraction.purchase_order})
    temporary = index_path.with_suffix(".tmp")
    temporary.write_text(index.model_dump_json(indent=2))
    temporary.replace(index_path)
    logger.info("[BATCH] Indexed %s PDFs; refreshed %s native order references", len(files), changed)
    return index
