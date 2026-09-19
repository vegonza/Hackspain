import os
import signal
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from threading import Event
from uuid import UUID

from redis import Redis
from redis.lock import Lock

from invoices.queue import PROCESSING, QUEUE, RETRIES, SCHEDULED, promote_retries
from invoices.repository import read_invoice_detail, write_invoice
from invoices.processing import process as process_invoice_record
from shared.logger import setup_logger
from shared.redis import get_redis
from shared.retries import MAX_ATTEMPTS, read_retry, record_failure

logger = setup_logger()


def process_invoice(invoice_id: str) -> None:
    with get_redis() as redis:
        state = read_retry(redis, RETRIES, invoice_id)
        if state.failed:
            return
        if state.attempts >= MAX_ATTEMPTS:
            state.failed = True
            state.next_attempt = None
            redis.hset(RETRIES, invoice_id, state.model_dump_json())
            return
        state.attempts += 1
        state.next_attempt = None
        redis.hset(RETRIES, invoice_id, state.model_dump_json())
    invoice_record = read_invoice_detail(UUID(invoice_id))
    if invoice_record.status in ("ready", "error"):
        return
    invoice_record.status = "processing"
    write_invoice(invoice_record)
    logger.info("[QUEUE] Processing %s", invoice_record.name)
    process_invoice_record(invoice_record)
    invoice_record.status = "ready"
    write_invoice(invoice_record)
    logger.info("[QUEUE] Finished %s: %s", invoice_record.name, invoice_record.status)
    state.last_error = None
    with get_redis() as redis, redis.pipeline(transaction=True) as transaction:
        transaction.hset(RETRIES, invoice_id, state.model_dump_json())
        transaction.execute()


def finish_jobs(redis: Redis, active: dict[Future[None], str], done: set[Future[None]]) -> None:
    for job in done:
        invoice_id = active[job]
        try:
            job.result()
        except Exception as error:
            state = record_failure(read_retry(redis, RETRIES, invoice_id), error)
            logger.exception("[QUEUE] Attempt %s failed for %s; retry scheduled: %s", state.attempts, invoice_id, state.next_attempt)
            with redis.pipeline(transaction=True) as transaction:
                transaction.hset(RETRIES, invoice_id, state.model_dump_json())
                transaction.lrem(PROCESSING, 1, invoice_id)
                if state.next_attempt is not None:
                    transaction.zadd(SCHEDULED, {invoice_id: state.next_attempt})
                transaction.execute()
        else:
            redis.lrem(PROCESSING, 1, invoice_id)
        del active[job]


def run_pool(redis: Redis, slots: int, stop: Event, lock: Lock) -> None:
    """Claim only available slots; each atomic move assigns one invoice once."""
    active: dict[Future[None], str] = {}
    logger.info("[QUEUE] Invoice worker pool started (%s slots)", slots)
    with ThreadPoolExecutor(max_workers=slots, thread_name_prefix="invoice") as pool:
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
                invoice_id = redis.brpoplpush(QUEUE, PROCESSING, timeout=1)
                if invoice_id is not None:
                    active[pool.submit(process_invoice, invoice_id)] = invoice_id
            except Exception:
                logger.exception("[QUEUE] Queue unavailable; preserving in-flight jobs")
                time.sleep(1)


def run() -> None:
    """A renewable Redis lease coordinates recovery and the processing pool."""
    slots = int(os.environ["INVOICE_WORKERS"])
    if slots < 1:
        raise ValueError("INVOICE_WORKERS must be positive")
    stop = Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    with get_redis() as redis:
        with redis.lock("invoices:worker-lock", timeout=120) as lock:
            while redis.rpoplpush(PROCESSING, QUEUE) is not None:
                pass
            run_pool(redis, slots, stop, lock)


if __name__ == "__main__":
    run()
