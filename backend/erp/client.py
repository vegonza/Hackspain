import os
from collections.abc import Callable
import re
import time
from types import TracebackType
from typing import Self
from urllib.parse import quote
from xml.etree import ElementTree

import httpx

from erp.errors import ErpProtocolError, ErpResponseError
from erp.models import ErpEntry, ErpPage, ErpSnapshot, ErpStatus
from erp.parsing import parse_entry
from erp.pages import parse_page
from erp.rate_limit import RateLimiter
from erp.status import parse_status
from erp.snapshots import download_snapshot
from shared.logger import get_logger

logger = get_logger()
TRANSIENT_NETWORK_ERRORS = (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError)


class ErpClient:
    """Sequential ERP session. Use as a context manager to release connections."""

    def __init__(
        self, base_url: str, username: str, password: str,
        *, transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._username = username
        self._password = password
        self._token: str | None = None
        self._limiter = RateLimiter()
        self._http = httpx.Client(
            base_url=base_url, timeout=10, follow_redirects=False,
            trust_env=False, transport=transport,
        )

    @classmethod
    def from_env(cls) -> Self:
        return cls(os.environ["ERP_BASE_URL"], os.environ["ERP_USERNAME"], os.environ["ERP_PASSWORD"])

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None,
        exc_value: BaseException | None, traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._token = None
        self._http.close()

    def _request(
        self, method: str, path: str, *, data: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> ElementTree.Element:
        self._limiter.wait()
        response = self._http.request(method, path, data=data, headers=headers)
        # Parse bytes so the XML declaration determines the character encoding.
        try:
            root = ElementTree.fromstring(response.content)
        except ElementTree.ParseError as exc:
            raise ErpProtocolError(f"Invalid XML from {path} (HTTP {response.status_code})") from exc
        if root.tag == "error":
            code = root.findtext("codigo")
            message = root.findtext("mensaje")
            if not code or not message:
                raise ErpProtocolError(f"Incomplete ERP error from {path}")
            logger.warning("[ERP] Request %s failed: %s", path, code)
            raise ErpResponseError(code, message, response.status_code, response.headers.get("Retry-After"))
        response.raise_for_status()
        return root

    def _wait_rate_limit(self, error: ErpResponseError, path: str, attempt: int) -> None:
        """The bridge supplies Retry-After as an integer number of seconds."""
        if error.retry_after is None or not re.fullmatch(r"[0-9]+", error.retry_after.strip()):
            raise ErpProtocolError("ERP-429 has no valid Retry-After in seconds") from error
        seconds = int(error.retry_after)
        logger.warning("[ERP] Retrying %s after ERP-429 in %ss (attempt %s/3)", path, seconds, attempt + 1)
        time.sleep(seconds)

    def _wait_backoff(self, error: httpx.TransportError | ErpProtocolError, path: str, attempt: int) -> None:
        seconds = 0.5 * 2 ** (attempt - 1)
        logger.warning(
            "[ERP] Retrying %s after %s in %ss (attempt %s/3)",
            path, type(error).__name__, seconds, attempt + 1,
        )
        time.sleep(seconds)

    def login(self) -> None:
        self._token = None
        attempt = 0
        while True:
            attempt += 1
            try:
                root = self._request("POST", "/erp/login", data={"usuario": self._username, "clave": self._password})
                token = root.findtext("token")
                if root.tag != "sesion" or not token or not token.strip():
                    raise ErpProtocolError("Login response has no session token")
                break
            except ErpProtocolError as exc:
                if attempt >= 3:
                    raise
                self._wait_backoff(exc, "/erp/login", attempt)
            except TRANSIENT_NETWORK_ERRORS as exc:
                if attempt >= 3:
                    raise
                self._wait_backoff(exc, "/erp/login", attempt)
            except ErpResponseError as exc:
                if exc.code != "ERP-429" or attempt >= 3:
                    raise
                self._wait_rate_limit(exc, "/erp/login", attempt)
        self._token = token
        logger.info("[ERP] Session established")

    def _get[T](
        self, path: str, parse: Callable[[ElementTree.Element], T], *, authenticated: bool = True,
    ) -> T:
        attempt = 0
        renewed_session = False
        while True:
            headers: dict[str, str] = {}
            if authenticated:
                if self._token is None:
                    self.login()
                assert self._token is not None
                headers["X-ERP-Token"] = self._token
            attempt += 1
            try:
                return parse(self._request("GET", path, headers=headers))
            except ErpProtocolError as exc:
                if attempt >= 3:
                    raise
                self._wait_backoff(exc, path, attempt)
            except TRANSIENT_NETWORK_ERRORS as exc:
                if attempt >= 3:
                    raise
                self._wait_backoff(exc, path, attempt)
            except ErpResponseError as exc:
                if exc.code == "SES-401":
                    self._token = None
                if attempt >= 3:
                    raise
                if exc.code == "ERP-429":
                    self._wait_rate_limit(exc, path, attempt)
                    continue
                if exc.code == "ORA-00600":
                    logger.warning("[ERP] Retrying %s after ORA-00600 (attempt %s/3)", path, attempt + 1)
                    continue
                if exc.code != "SES-401" or renewed_session or not authenticated:
                    raise
                logger.info("[ERP] Session expired; renewing")
                self.login()
                assert self._token is not None
                renewed_session = True

    def get_entry(self, entry_id: str) -> ErpEntry:
        def parse(root: ElementTree.Element) -> ErpEntry:
            entries = root.findall("./asientos/asiento")
            if root.tag != "respuesta" or len(entries) != 1:
                raise ErpProtocolError(f"Expected one ERP entry for {entry_id}")
            entry = parse_entry(entries[0])
            if entry.entry_id != entry_id:
                raise ErpProtocolError(f"ERP returned a different entry for {entry_id}")
            return entry

        entry = self._get("/erp/asientos/" + quote(entry_id, safe=""), parse)
        logger.info("[ERP] Retrieved entry %s", entry_id)
        return entry

    def get_page(self, number: int) -> ErpPage:
        def parse(root: ElementTree.Element) -> ErpPage:
            page = parse_page(root)
            if page.number != number:
                raise ErpProtocolError(f"ERP returned a different page for {number}")
            return page

        page = self._get(f"/erp/asientos?pagina={number}", parse)
        logger.info("[ERP] Retrieved page %s/%s (%s entries)", number, page.total_pages, len(page.entries))
        return page

    def get_status(self) -> ErpStatus:
        return self._get("/erp/estado", parse_status, authenticated=False)

    def get_snapshot(self) -> ErpSnapshot:
        return download_snapshot(self)
