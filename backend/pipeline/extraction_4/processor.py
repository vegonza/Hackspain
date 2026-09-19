import json
from hashlib import sha256

from documents.repository import DocumentSnapshot, save_document_features
from pipeline.erp import match_entry
from documents.stages import stage_attempt
from pipeline.extraction_4.features import extract_invoice_features
from pipeline.merge_3.quality import OCRCorrections
from pipeline.extraction_4.extractor import MODEL
from shared.logger import get_logger
from shared.storage import download_file, upload_file
from shared.usage import track_usage

logger = get_logger()


def process(document: DocumentSnapshot) -> None:
    prefix = f"{document.id}/extraction"
    result_path = f"{prefix}/features.json"
    with stage_attempt(document.id, document.name, "extraction", result_path):
        markdown = download_file(f"{document.id}/merge/document.md")
        corrections_bytes = download_file(f"{document.id}/merge/corrections.json")
        corrections = OCRCorrections.model_validate_json(corrections_bytes)
        logger.info("[EXTRACTION] Extracting invoice fields from combined text for %s", document.name)
        with track_usage("openrouter", MODEL, "extraction", str(document.id), document.name) as usage:
            features = extract_invoice_features(markdown.decode("utf-8"), usage=usage)
        features.uncertainties = list(dict.fromkeys([*features.uncertainties, *corrections.unresolved]))
        content = features.model_dump_json(indent=2).encode("utf-8")
        metadata = {
            "merged_sha256": sha256(markdown).hexdigest(),
            "corrections_sha256": sha256(corrections_bytes).hexdigest(),
            "features_sha256": sha256(content).hexdigest(),
            "model": MODEL,
        }
        upload_file(f"{prefix}/extraction.json", json.dumps(metadata).encode("utf-8"), "application/json")
        upload_file(result_path, content, "application/json")
        save_document_features(document.id, document.name, features)
        match_entry(document, features.purchase_order)
        logger.info("[EXTRACTION] Saved %s: %s line items, %s uncertainties",
                    document.name, len(features.line_items), len(features.uncertainties))
