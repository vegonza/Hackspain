import unittest
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth import APP_PASSWORD, COOKIE_NAME, LOGIN_ATTEMPT_LIMIT, PasswordMiddleware, router, session_token


class AuthenticationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.redis = MagicMock()
        self.redis.get.return_value = None
        self.redis.eval.return_value = [1, 900]
        redis_context = MagicMock()
        redis_context.__enter__.return_value = self.redis
        self.redis_patch = patch("auth.get_redis", return_value=redis_context)
        self.redis_patch.start()
        self.addCleanup(self.redis_patch.stop)

        app = FastAPI()
        app.add_middleware(PasswordMiddleware)
        app.include_router(router)

        @app.get("/api/private")
        def private() -> dict[str, bool]:
            return {"allowed": True}

        @app.get("/api/health")
        def health() -> dict[str, bool]:
            return {"healthy": True}

        self.client = TestClient(app)

    def test_private_api_requires_a_session(self) -> None:
        response = self.client.get("/api/private")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"detail": "authentication_required"})
        self.assertEqual(self.client.get("/api/health").status_code, 200)

    def test_login_rejects_an_invalid_password(self) -> None:
        response = self.client.post("/api/auth/login", json={"password": APP_PASSWORD + "-incorrect"})
        self.assertEqual(response.status_code, 401)
        self.assertNotIn(COOKIE_NAME, self.client.cookies)

    def test_login_is_rate_limited_after_five_failed_attempts(self) -> None:
        self.redis.eval.return_value = [LOGIN_ATTEMPT_LIMIT, 742]

        response = self.client.post("/api/auth/login", json={"password": APP_PASSWORD + "-incorrect"})

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json(), {"detail": "login_rate_limited"})
        self.assertEqual(response.headers["Retry-After"], "742")

    def test_login_remains_blocked_during_the_rate_limit_window(self) -> None:
        self.redis.get.return_value = str(LOGIN_ATTEMPT_LIMIT)
        self.redis.ttl.return_value = 511

        response = self.client.post("/api/auth/login", json={"password": APP_PASSWORD})

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["Retry-After"], "511")
        self.redis.eval.assert_not_called()

    def test_login_cookie_unlocks_the_api(self) -> None:
        response = self.client.post("/api/auth/login", json={"password": APP_PASSWORD})
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.client.cookies[COOKIE_NAME], session_token())
        self.redis.delete.assert_called_once()
        self.assertEqual(self.client.get("/api/auth/session").status_code, 204)
        self.assertEqual(self.client.get("/api/private").json(), {"allowed": True})


if __name__ == "__main__":
    unittest.main()
