import random
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx
from openai import PermissionDeniedError
from pydantic import BaseModel
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError

MAX_ATTEMPTS = 5


class RetryState(BaseModel):
    attempts: int = 0
    last_error: str | None = None
    next_attempt: float | None = None
    failed: bool = False


def read_retry(redis: Redis, key: str, identifier: str) -> RetryState:
    payload = redis.hget(key, identifier)
    return RetryState.model_validate_json(payload) if payload is not None else RetryState()


def status_code(error: Exception) -> int | None:
    status = getattr(error, "status_code", None)
    if status is None:
        status = getattr(error, "status", None)
    response = getattr(error, "response", None)
    if status is None and response is not None:
        status = response.status_code
    return int(status) if status is not None else None


def retryable(error: Exception) -> bool:
    status = status_code(error)
    if status is not None:
        return status in (408, 429) or 500 <= status <= 599
    return isinstance(error, (httpx.TransportError, TimeoutError, ConnectionError, RedisConnectionError, RedisTimeoutError)) or getattr(error, "code", None) in (
        "08000", "08001", "08003", "08006", "53300", "57P01", "57P02", "57P03", "PGRST000", "PGRST001", "PGRST002",
    )


def retry_delay(error: Exception, attempt: int) -> float:
    delay = min(60, 2 ** attempt) * random.uniform(0.8, 1.2)
    response = getattr(error, "response", None)
    headers = response.headers if response is not None else getattr(error, "headers", {})
    retry_after = headers.get("retry-after")
    if retry_after is not None:
        try:
            seconds = float(retry_after)
        except ValueError:
            try:
                seconds = (parsedate_to_datetime(retry_after) - datetime.now(timezone.utc)).total_seconds()
            except (ValueError, TypeError, OverflowError):
                seconds = 0
        delay = max(delay, seconds)
    return delay


def record_failure(state: RetryState, error: Exception) -> RetryState:
    status = status_code(error)
    state.last_error = f"{type(error).__name__}" + (f" (HTTP {status})" if status is not None else "")
    if isinstance(error, PermissionDeniedError) and isinstance(error.body, dict):
        message = error.body.get("message", "")
        if isinstance(message, str) and message.startswith("Key limit exceeded"):
            state.last_error = "openrouter_key_limit_exceeded"
    state.failed = state.attempts >= MAX_ATTEMPTS or not retryable(error)
    state.next_attempt = None if state.failed else time.time() + retry_delay(error, state.attempts)
    return state
