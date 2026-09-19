from threading import Event, Thread

from redis import Redis

from shared.logger import get_logger
from shared.redis import get_redis
from shared.usage import USAGE_OUTBOX, UsageRecord, save_usage

logger = get_logger()


def flush_usage(redis: Redis) -> None:
    """Acknowledge only persisted records; retries upsert the same immutable ID."""
    for usage_id, payload in redis.hscan_iter(USAGE_OUTBOX, count=100):
        try:
            record = UsageRecord.model_validate_json(payload)
            save_usage(record)
            redis.hdel(USAGE_OUTBOX, usage_id)
            logger.info("[USAGE] Saved %s / %s for %s", record.provider, record.model, record.document_name)
        except Exception:
            logger.exception("[USAGE] Persistence failed; keeping %s queued for retry", usage_id)


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
