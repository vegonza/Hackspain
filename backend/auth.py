import hashlib
import hmac
import logging
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from redis import Redis
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from shared.redis import get_redis


# This is a demo app. This basic password gate only prevents leaving the demo openly accessible;
# it is not intended to be secure authentication or a production security boundary.
APP_PASSWORD = os.environ["APP_PASSWORD"]
COOKIE_NAME = "humanos_session"
SESSION_MESSAGE = b"humanos-authenticated"
PUBLIC_PATHS = {"/api/auth/login", "/api/health"}
LOGIN_ATTEMPT_LIMIT = 5
LOGIN_WINDOW_SECONDS = 15 * 60
LOGIN_RATE_LIMIT_SCRIPT = """
local attempts = redis.call('INCR', KEYS[1])
if attempts == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return {attempts, redis.call('TTL', KEYS[1])}
"""
logger = logging.getLogger(__name__)


class LoginRequest(BaseModel):
    password: str


def session_token() -> str:
    return hmac.new(APP_PASSWORD.encode(), SESSION_MESSAGE, hashlib.sha256).hexdigest()


def authenticated(request: Request) -> bool:
    token = request.cookies.get(COOKIE_NAME, "")
    return hmac.compare_digest(token, session_token())


def login_rate_limit_key(request: Request) -> str:
    client_hash = hashlib.sha256(request.client.host.encode()).hexdigest()
    return f"auth:login:{client_hash}"


def blocked_retry_after(redis: Redis, key: str) -> int | None:
    attempts = redis.get(key)
    if attempts is None or int(attempts) < LOGIN_ATTEMPT_LIMIT:
        return None
    return max(redis.ttl(key), 1)


def record_failed_login(redis: Redis, key: str) -> tuple[int, int]:
    result = redis.eval(LOGIN_RATE_LIMIT_SCRIPT, 1, key, LOGIN_WINDOW_SECONDS)
    return int(result[0]), max(int(result[1]), 1)


def raise_rate_limited(retry_after: int, key: str) -> None:
    logger.warning("[AUTH] Login rate limit reached for %s", key.removeprefix("auth:login:")[:12])
    raise HTTPException(
        status_code=429,
        detail="login_rate_limited",
        headers={"Retry-After": str(retry_after)},
    )


class PasswordMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path.startswith("/api") and request.url.path not in PUBLIC_PATHS and not authenticated(request):
            return JSONResponse(status_code=401, content={"detail": "authentication_required"})
        return await call_next(request)


router = APIRouter(prefix="/api/auth")


@router.post("/login", status_code=204)
def login(credentials: LoginRequest, request: Request) -> Response:
    key = login_rate_limit_key(request)
    with get_redis() as redis:
        retry_after = blocked_retry_after(redis, key)
        if retry_after is not None:
            raise_rate_limited(retry_after, key)
        if not hmac.compare_digest(credentials.password, APP_PASSWORD):
            attempts, retry_after = record_failed_login(redis, key)
            if attempts >= LOGIN_ATTEMPT_LIMIT:
                raise_rate_limited(retry_after, key)
            raise HTTPException(status_code=401, detail="invalid_password")
        redis.delete(key)
    response = Response(status_code=204)
    response.set_cookie(
        COOKIE_NAME,
        session_token(),
        httponly=True,
        secure=os.environ["ENV"] == "production",
        samesite="strict",
        max_age=60 * 60 * 24 * 30,
    )
    return response


@router.get("/session", status_code=204)
def session() -> Response:
    return Response(status_code=204)
