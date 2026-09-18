from shared.logger import get_logger
from shared.redis import get_redis

QUEUE = "documents:queue"
PROCESSING = "documents:processing"
logger = get_logger()


def enqueue(document_id: str, name: str) -> None:
    with get_redis() as redis:
        redis.lpush(QUEUE, document_id)
    logger.info("[QUEUE] Queued %s (%s)", name, document_id)
