import os
import threading

from supabase import Client, ClientOptions, create_client

from shared.logger import get_logger
from shared.redis import get_redis

logger = get_logger()
_local = threading.local()
SIGNED_URL_LIFETIME = 3600
SIGNED_URL_CACHE_TTL = 3300


def signed_url_cache_key(path: str) -> str:
    return f"storage:signed-url:{os.environ['SUPABASE_STORAGE_BUCKET']}:{path}"


def invalidate_document_urls(document_id: str) -> None:
    with get_redis() as redis:
        for key in redis.scan_iter(match=signed_url_cache_key(f"{document_id}/*")):
            redis.unlink(key)


def get_client() -> Client:
    """Keep a separate Supabase client for each API worker thread."""
    client = getattr(_local, "client", None)
    if client is None:
        client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SECRET_KEY"],
            options=ClientOptions(storage_client_timeout=120),
        )
        _local.client = client
    return client


def upload_file(path: str, content: bytes, content_type: str) -> None:
    get_client().storage.from_(os.environ["SUPABASE_STORAGE_BUCKET"]).upload(
        path, content, {"content-type": content_type, "upsert": "true"},
    )
    with get_redis() as redis:
        redis.unlink(signed_url_cache_key(path))
    logger.info("[STORAGE] Uploaded %s", path)


def download_file(path: str) -> bytes:
    return get_client().storage.from_(os.environ["SUPABASE_STORAGE_BUCKET"]).download(path)


def signed_url(path: str) -> str:
    """Reuse signed URLs, expiring the cache five minutes before the signature."""
    key = signed_url_cache_key(path)
    with get_redis() as redis:
        cached = redis.get(key)
        if cached is not None:
            return cached
        result = get_client().storage.from_(os.environ["SUPABASE_STORAGE_BUCKET"]).create_signed_url(
            path, SIGNED_URL_LIFETIME,
        )
        url = result["signedURL"]
        redis.set(key, url, ex=SIGNED_URL_CACHE_TTL)
        return url
