import os
import signal
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from threading import Event
from uuid import UUID

from redis import Redis
from redis.lock import Lock

from documents.queue import PROCESSING, QUEUE, RETRIES, SCHEDULED, promote_retries
from documents.repository import read_document_detail, write_document
from pipeline.runner import run_pipeline
from shared.logger import setup_logger
from shared.redis import get_redis
from shared.retries import MAX_ATTEMPTS, read_retry, record_failure

logger = setup_logger()


def process_document(document_id: str) -> None:
    with get_redis() as redis:
        state = read_retry(redis, RETRIES, document_id)
        if state.failed:
            return
        if state.attempts >= MAX_ATTEMPTS:
            state.failed = True
            state.next_attempt = None
            redis.hset(RETRIES, document_id, state.model_dump_json())
            return
        state.attempts += 1
        state.next_attempt = None
        redis.hset(RETRIES, document_id, state.model_dump_json())
    document = read_document_detail(UUID(document_id))
    if document.status in ("ready", "error"):
        return
    document.status = "processing"
    write_document(document)
    logger.info("[QUEUE] Processing %s", document.name)
    run_pipeline(document)
    document.status = "ready"
    write_document(document)
    logger.info("[QUEUE] Finished %s: %s", document.name, document.status)
    state.last_error = None
    with get_redis() as redis, redis.pipeline(transaction=True) as transaction:
        transaction.delete(f"documents:ocr:{document_id}")
        transaction.hset(RETRIES, document_id, state.model_dump_json())
        transaction.execute()


def finish_jobs(redis: Redis, active: dict[Future[None], str], done: set[Future[None]]) -> None:
    for job in done:
        document_id = active[job]
        try:
            job.result()
        except Exception as error:
            state = record_failure(read_retry(redis, RETRIES, document_id), error)
            logger.exception("[QUEUE] Attempt %s failed for %s; retry scheduled: %s", state.attempts, document_id, state.next_attempt)
            with redis.pipeline(transaction=True) as transaction:
                transaction.hset(RETRIES, document_id, state.model_dump_json())
                transaction.lrem(PROCESSING, 1, document_id)
                if state.next_attempt is not None:
                    transaction.zadd(SCHEDULED, {document_id: state.next_attempt})
                transaction.execute()
        else:
            redis.lrem(PROCESSING, 1, document_id)
        del active[job]


def run_pool(redis: Redis, slots: int, stop: Event, lock: Lock) -> None:
    """Claim only available slots; each atomic move assigns one document once."""
    active: dict[Future[None], str] = {}
    logger.info("[QUEUE] Document worker pool started (%s slots)", slots)
    with ThreadPoolExecutor(max_workers=slots, thread_name_prefix="document") as pool:
        while not stop.is_set() or active:
            lock.reacquire()
            try:
                done = {job for job in active if job.done()}
                finish_jobs(redis, active, done)
                promote_retries()
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
    """A renewable Redis lease coordinates recovery and the processing pool."""
    slots = int(os.environ["DOCUMENT_WORKERS"])
    if slots < 1:
        raise ValueError("DOCUMENT_WORKERS must be positive")
    stop = Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    with get_redis() as redis:
        with redis.lock("documents:worker-lock", timeout=120) as lock:
            while redis.rpoplpush(PROCESSING, QUEUE) is not None:
                pass
            run_pool(redis, slots, stop, lock)


if __name__ == "__main__":
    run()
