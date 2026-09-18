import fcntl
import os
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from threading import Event
from uuid import UUID

from redis import Redis

from documents.queue import PROCESSING, QUEUE
from documents.repository import DATA_DIR, document_directory, read_document, write_document
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


def finish_jobs(redis: Redis, active: dict[Future[None], str], done: set[Future[None]]) -> None:
    for job in done:
        document_id = active[job]
        try:
            job.result()
        except Exception:
            logger.exception("[QUEUE] Job interrupted; requeuing %s", document_id)
            with redis.pipeline(transaction=True) as transaction:
                transaction.lrem(PROCESSING, 1, document_id)
                transaction.lpush(QUEUE, document_id)
                transaction.execute()
        else:
            redis.lrem(PROCESSING, 1, document_id)
        del active[job]


def run_pool(redis: Redis, slots: int, stop: Event) -> None:
    """Claim only available slots; each atomic move assigns one document once."""
    active: dict[Future[None], str] = {}
    logger.info("[QUEUE] Document worker pool started (%s slots)", slots)
    with ThreadPoolExecutor(max_workers=slots, thread_name_prefix="document") as pool:
        while not stop.is_set() or active:
            try:
                done = {job for job in active if job.done()}
                finish_jobs(redis, active, done)
                if stop.is_set() or len(active) == slots:
                    if active:
                        wait(active, timeout=1, return_when=FIRST_COMPLETED)
                    continue
                document_id = redis.brpoplpush(QUEUE, PROCESSING, timeout=1)
                if document_id is not None:
                    active[pool.submit(process_document, document_id)] = document_id
            except Exception:
                logger.exception("[QUEUE] Queue unavailable; preserving in-flight jobs")
                time.sleep(1)


def run() -> None:
    """One pool owns the shared metadata and recovers unfinished work on startup."""
    slots = int(os.environ["DOCUMENT_WORKERS"])
    if slots < 1:
        raise ValueError("DOCUMENT_WORKERS must be positive")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with (DATA_DIR / ".worker.lock").open("w") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        with get_redis() as redis:
            while redis.rpoplpush(PROCESSING, QUEUE) is not None:
                pass
            run_pool(redis, slots, Event())


if __name__ == "__main__":
    run()
