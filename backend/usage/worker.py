from threading import Event, Thread
import time

from redis import Redis

from shared.logger import get_logger
from shared.redis import get_redis
from shared.usage import USAGE_OUTBOX, UsageRecord, save_usage
from shared.retries import MAX_ATTEMPTS, read_retry, record_failure

logger = get_logger()
RETRIES = "usage:retries"


def flush_usage(redis: Redis) -> None:
    """Acknowledge only persisted records; retries upsert the same immutable ID."""
    for usage_id, payload in redis.hscan_iter(USAGE_OUTBOX, count=100):
        lock = redis.lock(f"usage:lock:{usage_id}", timeout=180)
        if not lock.acquire(blocking=False):
            continue
        try:
            persist_pending(redis, usage_id, payload)
        finally:
            lock.release()


def persist_pending(redis: Redis, usage_id: str, payload: str) -> None:
    if not redis.hexists(USAGE_OUTBOX, usage_id):
        return
    state = read_retry(redis, RETRIES, usage_id)
    if state.failed or (state.next_attempt is not None and state.next_attempt > time.time()):
        return
    if state.attempts >= MAX_ATTEMPTS:
        state.failed = True
        state.next_attempt = None
        redis.hset(RETRIES, usage_id, state.model_dump_json())
        return
    state.attempts += 1
    state.next_attempt = None
    redis.hset(RETRIES, usage_id, state.model_dump_json())
    try:
        record = UsageRecord.model_validate_json(payload)
        save_usage(record)
        with redis.pipeline(transaction=True) as transaction:
            transaction.hdel(USAGE_OUTBOX, usage_id)
            transaction.hdel(RETRIES, usage_id)
            transaction.execute()
        logger.info("[USAGE] Saved %s / %s for %s", record.provider, record.model, record.document_name)
    except Exception as error:
        state = record_failure(state, error)
        redis.hset(RETRIES, usage_id, state.model_dump_json())
        logger.exception("[USAGE] Attempt %s failed for %s; retry scheduled: %s", state.attempts, usage_id, state.next_attempt)


def run(stop: Event) -> None:
    logger.info("[USAGE] Persistence worker started")
    with get_redis() as redis:
        while not stop.is_set():
            try:
                flush_usage(redis)
            except Exception:
                logger.exception("[USAGE] Redis unavailable; retrying")
            stop.wait(5)


def start_usage_worker() -> tuple[Event, Thread]:
    stop = Event()
    thread = Thread(target=run, args=(stop,), daemon=True, name="usage-worker")
    thread.start()
    return stop, thread
