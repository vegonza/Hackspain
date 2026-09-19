from time import monotonic, sleep


class RateLimiter:
    """Space requests from one sequential client, including login and retries."""

    def __init__(self) -> None:
        self._next_request_at = 0.0

    def wait(self) -> None:
        delay = self._next_request_at - monotonic()
        if delay > 0:
            sleep(delay)
        self._next_request_at = monotonic() + 1 / 9
