import time
from uuid import UUID

from documents.queue import PROCESSING, QUEUE
from documents.repository import document_directory, read_document, write_document
from documents.processor import extract_markdown
from shared.logger import setup_logger
from shared.redis import get_redis
from shared.storage import download_file, upload_file

logger = setup_logger()


def process_document(document_id: str) -> None:
    directory = document_directory(UUID(document_id))
    document = read_document(directory)
    if document.status in ("ready", "error"):
        return
    document.status = "processing"
    write_document(directory, document)
    logger.info("[QUEUE] Processing %s", document.name)
    try:
        pdf = download_file(f"{document_id}/original.pdf")
        markdown, pages = extract_markdown(pdf, document_id)
        upload_file(f"{document_id}/document.md", markdown.encode("utf-8"), "text/markdown; charset=utf-8")
        document.pages = pages
        document.status = "ready"
    except Exception:
        document.status = "error"
        logger.exception("[QUEUE] Processing failed for %s", document.name)
    write_document(directory, document)
    logger.info("[QUEUE] Finished %s: %s", document.name, document.status)


def run() -> None:
    """A single worker resumes its in-flight item before taking the next FIFO item."""
    with get_redis() as redis:
        while True:
            try:
                document_id = redis.lindex(PROCESSING, 0)
                if document_id is None:
                    document_id = redis.brpoplpush(QUEUE, PROCESSING, timeout=1)
                if document_id is None:
                    continue
                process_document(document_id)
                redis.lrem(PROCESSING, 1, document_id)
            except Exception:
                logger.exception("[QUEUE] Worker interrupted; keeping the job for retry")
                time.sleep(1)


if __name__ == "__main__":
    run()
