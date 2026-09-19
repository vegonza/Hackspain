from documents.repository import Document
from documents.stages import stage_attempt
from pipeline.merge_3.quality import compare_text, merge_text
from pipeline.extraction_4.extractor import MODEL
from shared.logger import get_logger
from shared.storage import download_file, upload_file
from shared.usage import track_usage

logger = get_logger()


def process(document: Document) -> None:
    prefix = f"{document.id}/merge"
    result_path = f"{prefix}/document.md"
    with stage_attempt(document.id, document.name, "merge", result_path):
        native = download_file(f"{document.id}/native.txt").decode("utf-8")
        markdown = download_file(f"{document.id}/document.md").decode("utf-8")
        report = compare_text(native, markdown)
        upload_file(f"{prefix}/quality.json", report.model_dump_json().encode("utf-8"), "application/json")
        logger.info("[MERGE] Combining native text and OCR for %s", document.name)
        with track_usage("openrouter", MODEL, "merge", str(document.id), document.name) as usage:
            merged, corrections = merge_text(native, markdown, usage=usage)
        upload_file(f"{prefix}/corrections.json", corrections.model_dump_json().encode("utf-8"), "application/json")
        after = compare_text(native, merged)
        upload_file(f"{prefix}/quality-after.json", after.model_dump_json().encode("utf-8"), "application/json")
        upload_file(result_path, merged.encode("utf-8"), "text/markdown; charset=utf-8")
        logger.info("[MERGE] Combined %s: %s corrections, %s unresolved issues",
                    document.name, len(corrections.corrections), len(corrections.unresolved))
