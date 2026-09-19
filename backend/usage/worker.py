import time

from redis import Redis

from shared.logger import setup_logger
from shared.redis import get_redis
from shared.usage import USAGE_OUTBOX, UsageRecord, save_usage

logger = setup_logger()


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


def run() -> None:
    logger.info("[USAGE] Persistence worker started")
    with get_redis() as redis:
        while True:
            try:
                flush_usage(redis)
            except Exception:
                logger.exception("[USAGE] Redis unavailable; retrying")
            time.sleep(5)


if __name__ == "__main__":
    run()
