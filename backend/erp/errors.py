class ErpResponseError(Exception):
    """An ERP rejection, retaining the information needed by the retry policy."""

    def __init__(self, code: str, message: str, status: int, retry_after: str | None) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.status = status
        self.retry_after = retry_after


class ErpProtocolError(Exception):
    """The bridge returned malformed XML or an unexpected response structure."""
