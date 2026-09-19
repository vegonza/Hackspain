import time

from shared.logger import get_logger
from shared.redis import get_redis

QUEUE = "invoices:queue"
PROCESSING = "invoices:processing"
RETRIES = "invoices:retries"
SCHEDULED = "invoices:scheduled"
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


def enqueue(invoice_id: str, name: str) -> None:
    with get_redis() as redis:
        redis.lpush(QUEUE, invoice_id)
    logger.info("[QUEUE] Queued %s (%s)", name, invoice_id)
