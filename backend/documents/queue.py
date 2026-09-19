import time

from shared.logger import get_logger
from shared.redis import get_redis

QUEUE = "documents:queue"
PROCESSING = "documents:processing"
RETRIES = "documents:retries"
SCHEDULED = "documents:scheduled"
logger = get_logger()


def promote_retries() -> None:
    """Atomically move due retries to the ready queue without occupying a worker."""
    with get_redis() as redis:
        redis.eval("""
            local ids = redis.call('ZRANGEBYSCORE', KEYS[1], '-inf', ARGV[1], 'LIMIT', 0, 100)
            for _, id in ipairs(ids) do
                redis.call('ZREM', KEYS[1], id)
                redis.call('LPUSH', KEYS[2], id)
            end
            return #ids
        """, 2, SCHEDULED, QUEUE, time.time())


def enqueue(document_id: str, name: str) -> None:
    with get_redis() as redis:
        redis.lpush(QUEUE, document_id)
    logger.info("[QUEUE] Queued %s (%s)", name, document_id)
