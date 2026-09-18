import os

from redis import Redis


def get_redis() -> Redis:
    return Redis.from_url(
        os.environ["REDIS_URL"], decode_responses=True,
        socket_connect_timeout=5, socket_timeout=5,
    )
