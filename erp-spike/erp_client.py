#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hardened client for the "ERP Miralmar 2009" legacy bridge (alberto_erp.py).

This module is the *integration layer*: it is the only component allowed to
talk to the ERP. It absorbs every quirk of the legacy system and exposes a
clean, normalized snapshot to the rest of the pipeline.

IMPORTANT SCOPE NOTE
--------------------
This layer reports FACTS and DATA-QUALITY OBSERVATIONS. It never makes
business decisions. The words PAY / DO_NOT_PAY / ESCALATE do not appear
anywhere in this file, on purpose (see docs/ADR.md, ADR-011).

ERP LIMITATIONS HANDLED
-----------------------
  1. Authentication is mandatory for every data endpoint.
  2. Tokens expire after 900 s OR 300 uses, whichever comes first. We renew
     proactively at 780 s / 250 uses. Both thresholds and the clock itself
     are constructor arguments, so the expiry logic is covered by real tests
     instead of by argument.
  3. ORA-00600 is injected on every 10th authenticated query. The counter is
     global to the server process and survives re-login. Because two
     multiples of ten are never consecutive, a single sequential client is
     mathematically guaranteed to succeed on immediate retry.
  4. More than 10 requests per second returns ERP-429. Rejected requests are
     ALSO recorded in the server window, so retrying without waiting keeps
     you blocked. We self-throttle instead. The 429 carries a `Retry-After`
     header, which we obey when it asks for longer than our own cooldown,
     ignore when it asks for less, and cap so that a misconfigured server
     cannot stall the run.
  5. 120 ms of artificial latency per request (0 ms with --rapido).
  6. Responses are XML encoded in ISO-8859-1 with errors="replace".
  7. Dates are DD/MM/YYYY, amounts use Spanish grouping ("12.874,40").
  8. Malformed source data is echoed back verbatim by the server, so the
     parser must tolerate and flag rather than crash.
  9. Results are paginated 20 at a time; out-of-range pages return ERP-400.
 10. Duplicate entry ids are possible: the listing shows both, the detail
     endpoint shows only the last one.
 11. The Saturday batch is merged by entry id and appended at the end.

SECURITY POSTURE
----------------
  * The session token is sent in the X-ERP-Token header, never in the query
    string, so it does not end up in server logs.
  * System proxies are explicitly disabled: this traffic must never leave
    the machine.
  * HTTP redirects are refused, so the token cannot be replayed to a
    different host.
  * Response bodies are capped, so a runaway server cannot exhaust memory.
  * Credentials are read from the environment; the literals below are the
    published defaults from the challenge manual.
  * Path segments are strictly validated and fully percent-encoded.

USAGE
-----
    python3 erp_client.py status
    python3 erp_client.py dump --output data/erp_entries.jsonl
    python3 erp_client.py probe --count 25
    python3 erp_client.py selftest

EXIT CODES
----------
    0   success
    1   completed but diagnostics failed (incomplete or inconsistent data)
    2   ERP unreachable
    3   permanent ERP error (bad credentials, bad request, protocol error)
    4   invalid command line usage
  130   interrupted by the user

Standard library only. Tested on CPython 3.13.
"""

from __future__ import annotations

import argparse
import email.utils
import json
import os
import re
import socket
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence, TypeVar

__version__ = "2.2.0"

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Published in MANUAL_ERP_2009.md. Overridable so that no credential is ever
# *required* to live in source control.
DEFAULT_BASE_URL = os.environ.get("ERP_BASE_URL", "http://127.0.0.1:8009")
ERP_USERNAME = os.environ.get("ERP_USERNAME", "alberto")
ERP_PASSWORD = os.environ.get("ERP_PASSWORD", "FACTURAS2009")

# The server rejects >10 requests per second. 8 leaves comfortable headroom
# and still completes a full dump in under four seconds.
DEFAULT_REQUESTS_PER_SECOND = 8.0

# The server expires sessions at 300 uses / 900 s. Renew early.
# Exposed as constructor arguments so the expiry logic can be exercised in
# a test without making 250 requests or waiting thirteen minutes.
DEFAULT_SESSION_MAX_USES = 250
DEFAULT_SESSION_MAX_AGE_SECONDS = 780.0

REQUEST_TIMEOUT_SECONDS = 10.0
DEFAULT_MAX_ATTEMPTS = 8
DEFAULT_TIME_BUDGET_SECONDS = 300.0
DEFAULT_BACKOFF_BASE_SECONDS = 0.25
DEFAULT_BACKOFF_CAP_SECONDS = 4.0

# The largest legitimate response is a 20-entry page, well under 8 KiB.
# 8 MiB is a generous ceiling that still bounds memory and mitigates
# XML expansion attacks.
DEFAULT_MAX_RESPONSE_BYTES = 8 * 1024 * 1024

# A full window must drain before the server forgives a rate-limit rejection.
# This is the *floor*: we never wait less than this, even if the server asks
# us to come back sooner. The server's own window is a strict `>` over a
# sliding second, so 1.0 s is cutting it fine; 1.1 s is not.
DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS = 1.1

# The server sends `Retry-After` on every 429. Today it always says 1, which
# our floor already covers, but the Saturday build is free to raise it and we
# would rather obey than be throttled again. This is the *ceiling*: a remote
# party must not be able to park us for an arbitrary length of time.
MAX_RETRY_AFTER_SECONDS = 30.0

KNOWN_STATUSES = frozenset({"PENDIENTE", "PAGADA"})
ENTRY_XML_FIELDS = ("id", "fecha", "proveedor", "nif", "pedido", "importe", "estado")

# Entry and order identifiers we are willing to place inside a URL path.
#
# Every pattern here is anchored with \Z rather than $. In Python, $ also
# matches immediately before a trailing newline, so "AS-1\n" would sail
# through a $-anchored check. \Z means end of string and nothing else.
SAFE_PATH_SEGMENT = re.compile(r"^[A-Za-z0-9._-]{1,64}\Z")

# Numeric-looking amount: a digit, then digits and separators only.
AMOUNT_SHAPE = re.compile(r"^[+-]?[0-9][0-9.,]*\Z")

# Well-formed thousands grouping: 1-3 digits, then groups of exactly 3.
_GROUPED_DOT = re.compile(r"^\d{1,3}(?:\.\d{3})+\Z")
_GROUPED_COMMA = re.compile(r"^\d{1,3}(?:,\d{3})+\Z")

ID_SERIES = re.compile(r"^(?P<prefix>[A-Za-z-]+)(?P<number>\d+)\Z")

# Two identifiers further apart than this are considered different series
# rather than a gap. Prevents reporting AS-00518 -> AS-70001 as 69 482 holes.
MAX_REPORTED_GAP = 20


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class ErpUnavailable(Exception):
    """The ERP could not be reached, or retries were exhausted."""


class ErpPermanentError(Exception):
    """The ERP refused the request and retrying cannot help."""

    def __init__(self, code: str, message: str, status: int = 0) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message
        self.status = status


class ErpProtocolError(Exception):
    """The ERP answered with something we cannot interpret.

    Treated as transient: a truncated body is usually a dropped connection,
    which the very next attempt will not reproduce.
    """


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

class RateLimiter:
    """Enforces a minimum interval between outgoing requests.

    A sliding window like the server's is unnecessary: this client is
    strictly sequential, so spacing every request by 1/rate seconds keeps
    the instantaneous rate below the threshold in any one-second window.

    The clock and the sleep function are injectable. Real time is the
    default; tests substitute a fake clock so that "we waited eleven
    seconds" can be asserted without anybody waiting eleven seconds.
    """

    def __init__(
        self,
        requests_per_second: float,
        clock: "Callable[[], float] | None" = None,
        sleeper: "Callable[[float], None] | None" = None,
    ) -> None:
        if requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive")
        self.interval = 1.0 / requests_per_second
        self._clock = clock or time.monotonic
        self._sleep = sleeper or time.sleep
        self._next_allowed = self._clock()

    def wait(self) -> None:
        now = self._clock()
        if now < self._next_allowed:
            self._sleep(self._next_allowed - now)
            now = self._clock()
        self._next_allowed = now + self.interval

    def penalize(self, seconds: float) -> None:
        """Push the next allowed slot further into the future."""
        self._next_allowed = max(self._next_allowed, self._clock() + seconds)


def parse_retry_after(raw: "str | None", now: "float | None" = None) -> "float | None":
    """Turn a `Retry-After` header into a number of seconds, or None.

    RFC 9110 allows two forms: delta-seconds ("1") and an HTTP-date
    ("Wed, 21 Oct 2026 07:28:00 GMT"). The ERP only ever sends the first,
    but parsing both costs four lines and removes a class of surprise.

    The result is clamped to [0, MAX_RETRY_AFTER_SECONDS]. Anything we
    cannot make sense of returns None, which means "fall back to our own
    cooldown" rather than "do not wait".
    """
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None

    seconds: "float | None" = None
    try:
        seconds = float(int(text))          # delta-seconds, integer by spec
    except ValueError:
        try:
            when = email.utils.parsedate_to_datetime(text)
        except (TypeError, ValueError, OverflowError):
            return None
        if when is None:
            return None
        if when.tzinfo is None:             # naive dates are GMT per the RFC
            when = when.replace(tzinfo=timezone.utc)
        reference = now if now is not None else datetime.now(timezone.utc).timestamp()
        seconds = when.timestamp() - reference

    if seconds != seconds or seconds in (float("inf"), float("-inf")):  # NaN / inf
        return None
    return max(0.0, min(seconds, MAX_RETRY_AFTER_SECONDS))


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

@dataclass
class Metrics:
    """Everything needed to prove the client behaved well."""

    requests: int = 0
    successful_responses: int = 0
    retries_ora00600: int = 0
    retries_rate_limited: int = 0
    retries_session_expired: int = 0
    retries_protocol: int = 0
    retries_network: int = 0
    logins: int = 0
    elapsed_seconds: float = 0.0

    @property
    def total_retries(self) -> int:
        return (
            self.retries_ora00600
            + self.retries_rate_limited
            + self.retries_session_expired
            + self.retries_protocol
            + self.retries_network
        )

    def as_dict(self) -> "dict[str, Any]":
        return {
            "requests": self.requests,
            "successful_responses": self.successful_responses,
            "retries_ora00600": self.retries_ora00600,
            "retries_rate_limited": self.retries_rate_limited,
            "retries_session_expired": self.retries_session_expired,
            "retries_protocol": self.retries_protocol,
            "retries_network": self.retries_network,
            "total_retries": self.total_retries,
            "logins": self.logins,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
        }

    def summary(self) -> str:
        return (
            f"requests={self.requests} ok={self.successful_responses} "
            f"ORA-00600={self.retries_ora00600} 429={self.retries_rate_limited} "
            f"SES-401={self.retries_session_expired} "
            f"protocol={self.retries_protocol} network={self.retries_network} "
            f"logins={self.logins} elapsed={self.elapsed_seconds:.1f}s"
        )


# ---------------------------------------------------------------------------
# Tolerant parsers
#
# These never raise. They return (value, warning) so that the caller can
# record exactly what happened without losing the original text.
# ---------------------------------------------------------------------------

def parse_legacy_date(raw: str) -> "tuple[date | None, str | None]":
    """Parse a date emitted by the legacy bridge.

    The bridge normally formats dates as DD/MM/YYYY, but echoes the source
    value untouched when its own formatting fails. The source is an ISO
    date, so both shapes must be accepted.

    Returns (date, warning). A warning is produced when the value is
    unusable or when a fallback format had to be used.
    """
    text = (raw or "").strip()
    if not text:
        return None, None

    for fmt, warning in (("%d/%m/%Y", None), ("%Y-%m-%d", "date_in_iso_format")):
        try:
            parsed = datetime.strptime(text, fmt).date()
        except ValueError:
            continue
        # A plausibility band. Anything outside it is data corruption that
        # happens to be syntactically valid.
        if not (1900 <= parsed.year <= 2100):
            return None, f"date_out_of_range:{text!r}"
        return parsed, warning

    return None, f"date_unparseable:{text!r}"


def _is_well_formed_grouping(text: str, separator: str) -> bool:
    """True if text looks like 1.234.567 (or 1,234,567): leading group of
    1-3 digits followed by groups of exactly 3.

    Without this check, "12,34,56" would be silently read as 123456 and
    "1..2" as 12. Both are corruption, not formatting.
    """
    pattern = _GROUPED_DOT if separator == "." else _GROUPED_COMMA
    return bool(pattern.match(text))


def parse_legacy_amount(raw: str) -> "tuple[Decimal | None, str | None]":
    """Parse a monetary amount without ever guessing silently.

    The bridge emits Spanish grouping ("12.874,40"), but echoes the source
    value untouched when its own formatting fails. The source uses plain
    English decimals ("1234.56"). Blindly stripping dots would turn
    1 234,56 EUR into 123 456,00 EUR, so the separator is inferred instead:

      * both separators present  -> the rightmost one is the decimal mark
      * only commas              -> Spanish decimal, or English grouping if
                                    there is more than one
      * only dots                -> English decimal, unless followed by
                                    exactly three digits, which is genuinely
                                    ambiguous and therefore flagged
      * neither                  -> plain integer

    Any separator treated as grouping must form well-shaped groups of three
    digits; otherwise the value is corruption and is rejected outright.

    Returns (amount, warning). Never raises.
    """
    text = (raw or "").strip().replace("\u00a0", "").replace(" ", "")
    if not text:
        return None, None

    unparseable = (None, f"amount_unparseable:{raw.strip()!r}")

    if not AMOUNT_SHAPE.match(text):
        return unparseable

    sign = ""
    if text[0] in "+-":
        sign = "-" if text[0] == "-" else ""
        text = text[1:]
    if not text:
        return unparseable

    last_dot = text.rfind(".")
    last_comma = text.rfind(",")
    warning: "str | None" = None

    if last_dot >= 0 and last_comma >= 0:
        # Mixed separators: the rightmost one has to be the decimal mark.
        if last_comma > last_dot:
            decimal_sep, grouping_sep = ",", "."
        else:
            decimal_sep, grouping_sep = ".", ","
            warning = "amount_english_format"
        if text.count(decimal_sep) != 1:
            return unparseable
        integer_part, fraction = text.rsplit(decimal_sep, 1)
        if not fraction.isdigit() or not integer_part:
            return unparseable
        if not _is_well_formed_grouping(integer_part, grouping_sep):
            return unparseable
        normalized = integer_part.replace(grouping_sep, "") + "." + fraction

    elif last_comma >= 0:
        if text.count(",") > 1:
            # 1,234,567 -> English grouping, integer value.
            if not _is_well_formed_grouping(text, ","):
                return unparseable
            normalized = text.replace(",", "")
            warning = "amount_english_format"
        else:
            integer_part, fraction = text.split(",")
            if not integer_part.isdigit() or not fraction.isdigit():
                return unparseable
            if len(fraction) == 3:
                # "1,234" is irreducibly ambiguous. The bridge speaks
                # Spanish, so this is a decimal comma, but say so.
                warning = "amount_ambiguous_thousands"
            normalized = integer_part + "." + fraction

    elif last_dot >= 0:
        if text.count(".") > 1:
            # 1.234.567 -> Spanish grouping, integer value.
            if not _is_well_formed_grouping(text, "."):
                return unparseable
            normalized = text.replace(".", "")
        else:
            integer_part, fraction = text.split(".")
            if not integer_part.isdigit() or not fraction.isdigit():
                return unparseable
            if len(fraction) == 3:
                # "1.234": grouping is the better bet for a Spanish source,
                # but the caller must know the reading was a judgement call.
                normalized = integer_part + fraction
                warning = "amount_ambiguous_thousands"
            else:
                # "1234.56" or "1234.5": the English source leaking through
                # because the bridge failed to format it.
                normalized = text
                warning = "amount_english_format"
    else:
        normalized = text

    try:
        value = Decimal(sign + normalized)
    except InvalidOperation:
        return unparseable

    return value, warning


def _element_text(node: "ElementTree.Element | None") -> str:
    if node is None or node.text is None:
        return ""
    return node.text.strip()


def _safe_int(node: "ElementTree.Element | None", default: int = 0) -> int:
    try:
        return int(_element_text(node))
    except (TypeError, ValueError):
        return default


def _parse_xml(body: bytes, context: str) -> ElementTree.Element:
    """Parse bytes into an XML tree, converting every failure mode into
    ErpProtocolError so callers never see a raw traceback."""
    if not body:
        raise ErpProtocolError(f"{context}: empty response body")
    try:
        # Bytes, not str: the payload carries an encoding declaration and
        # ElementTree rejects declared encodings on str input.
        return ElementTree.fromstring(body)
    except ElementTree.ParseError as exc:
        preview = body[:120].decode("iso-8859-1", errors="replace")
        raise ErpProtocolError(
            f"{context}: malformed XML ({exc}); starts with {preview!r}"
        ) from exc


def _error_code(body: bytes) -> str:
    """Extract <error><codigo> from an error body, or '' if absent."""
    try:
        root = ElementTree.fromstring(body)
    except (ElementTree.ParseError, TypeError):
        return ""
    if root.tag != "error":
        return ""
    return _element_text(root.find("codigo"))


def _error_message(body: bytes) -> str:
    try:
        root = ElementTree.fromstring(body)
    except (ElementTree.ParseError, TypeError):
        return body[:200].decode("iso-8859-1", errors="replace")
    text = _element_text(root.find("mensaje"))
    return text or body[:200].decode("iso-8859-1", errors="replace")


# ---------------------------------------------------------------------------
# Normalized domain model
# ---------------------------------------------------------------------------

@dataclass
class Entry:
    """A single accounting entry, normalized, with its defects made explicit.

    Raw values are always preserved next to the parsed ones. That is what
    makes the output auditable, and it is how the amount-parsing defect was
    discovered in the first place.
    """

    entry_id: str          # ERP <id>,        e.g. "AS-00084"
    supplier_id: str       # ERP <proveedor>, e.g. "P002"
    tax_id: str            # ERP <nif>, the Spanish tax identifier
    order_id: str          # ERP <pedido>,    e.g. "PO-2026-0084"
    status: str            # ERP <estado>: PENDIENTE | PAGADA
    raw_date: str
    raw_amount: str
    date: "date | None" = None
    amount: "Decimal | None" = None
    warnings: "list[str]" = field(default_factory=list)

    @classmethod
    def from_xml(cls, node: ElementTree.Element) -> "Entry":
        raw = {name: _element_text(node.find(name)) for name in ENTRY_XML_FIELDS}
        entry = cls(
            entry_id=raw["id"],
            supplier_id=raw["proveedor"],
            tax_id=raw["nif"],
            order_id=raw["pedido"],
            status=raw["estado"],
            raw_date=raw["fecha"],
            raw_amount=raw["importe"],
        )

        entry.date, date_warning = parse_legacy_date(entry.raw_date)
        entry.amount, amount_warning = parse_legacy_amount(entry.raw_amount)
        if date_warning:
            entry.warnings.append(date_warning)
        if amount_warning:
            entry.warnings.append(amount_warning)

        if entry.status and entry.status not in KNOWN_STATUSES:
            entry.warnings.append(f"unknown_status:{entry.status!r}")

        # ISO-8859-1 with errors="replace" turns unrepresentable characters
        # into '?' at the source. The loss is irreversible; flag it.
        if "?" in (entry.supplier_id + entry.tax_id + entry.order_id):
            entry.warnings.append("possible_character_loss")

        for name in ("entry_id", "tax_id", "order_id", "supplier_id", "status"):
            if not getattr(entry, name):
                entry.warnings.append(f"empty_field:{name}")

        return entry

    def to_dict(self) -> "dict[str, Any]":
        return {
            "entry_id": self.entry_id,
            "supplier_id": self.supplier_id,
            "tax_id": self.tax_id,
            "order_id": self.order_id,
            "status": self.status,
            "raw_date": self.raw_date,
            "raw_amount": self.raw_amount,
            "date": self.date.isoformat() if self.date else None,
            # Serialized as a string on purpose: JSON numbers are IEEE 754
            # doubles and would silently destroy decimal precision.
            "amount": str(self.amount) if self.amount is not None else None,
            "warnings": list(self.warnings),
        }


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------

def find_id_gaps(identifiers: "Iterable[str]", max_gap: int = MAX_REPORTED_GAP) -> "list[str]":
    """Report identifiers that are missing from an otherwise contiguous run.

    The ERP data contains deliberate holes (no AS-70008, no AS-72004, ...).
    Those correspond to invoices with no accounting entry at all, which is
    decision-relevant information for the rules engine.

    Jumps larger than max_gap are treated as a change of series rather than
    a gap, so AS-00518 -> AS-70001 is not reported as 69 482 missing ids.
    """
    by_series: "dict[tuple[str, int], list[int]]" = {}
    for identifier in identifiers:
        match = ID_SERIES.match(identifier or "")
        if not match:
            continue
        key = (match.group("prefix"), len(match.group("number")))
        by_series.setdefault(key, []).append(int(match.group("number")))

    missing: "list[str]" = []
    for (prefix, width), numbers in sorted(by_series.items()):
        ordered = sorted(set(numbers))
        for current, following in zip(ordered, ordered[1:]):
            distance = following - current
            if 1 < distance <= max_gap:
                missing.extend(f"{prefix}{n:0{width}d}" for n in range(current + 1, following))
    return missing


def _duplicates(values: "Iterable[str]") -> "list[str]":
    seen: "dict[str, int]" = {}
    for value in values:
        if value:
            seen[value] = seen.get(value, 0) + 1
    return sorted(key for key, count in seen.items() if count > 1)


def build_diagnostics(
    entries: "Sequence[Entry]",
    declared_total: int,
    status_before: "dict[str, Any]",
    status_after: "dict[str, Any]",
) -> "dict[str, Any]":
    """Summarize what is trustworthy about this snapshot and what is not."""
    warning_counts: "dict[str, int]" = {}
    for entry in entries:
        for warning in entry.warnings:
            key = warning.split(":", 1)[0]
            warning_counts[key] = warning_counts.get(key, 0) + 1

    status_counts: "dict[str, int]" = {}
    for entry in entries:
        label = entry.status or "<empty>"
        status_counts[label] = status_counts.get(label, 0) + 1

    # If the server reloaded data mid-dump, the snapshot mixes two worlds.
    drift = (
        status_before.get("entry_count") != status_after.get("entry_count")
        or status_before.get("update_loaded") != status_after.get("update_loaded")
    )

    complete = declared_total == len(entries) and len(entries) > 0 and not drift

    return {
        "complete": complete,
        "declared_total": declared_total,
        "received_total": len(entries),
        "unique_entry_ids": len({e.entry_id for e in entries}),
        "duplicate_entry_ids": _duplicates(e.entry_id for e in entries),
        "duplicate_order_ids": _duplicates(e.order_id for e in entries),
        "missing_entry_ids": find_id_gaps(e.entry_id for e in entries),
        "entries_with_warnings": sum(1 for e in entries if e.warnings),
        "warning_counts": warning_counts,
        "status_counts": status_counts,
        "snapshot_drift": drift,
    }


@dataclass
class Snapshot:
    """An immutable, self-describing view of the ERP at a point in time."""

    entries: "list[Entry]"
    fetched_at: str
    erp_status_before: "dict[str, Any]"
    erp_status_after: "dict[str, Any]"
    diagnostics: "dict[str, Any]"
    metrics: Metrics

    @property
    def complete(self) -> bool:
        return bool(self.diagnostics.get("complete"))

    def by_order_id(self) -> "dict[str, Entry]":
        """Index by order id. Duplicates are reported in diagnostics; the
        last occurrence wins here, mirroring the ERP's own detail endpoint."""
        return {e.order_id: e for e in self.entries if e.order_id}

    def report(self) -> "dict[str, Any]":
        return {
            "client_version": __version__,
            "fetched_at": self.fetched_at,
            "erp_status_before": self.erp_status_before,
            "erp_status_after": self.erp_status_after,
            "diagnostics": self.diagnostics,
            "metrics": self.metrics.as_dict(),
        }


# ---------------------------------------------------------------------------
# HTTP plumbing
# ---------------------------------------------------------------------------

class _RefuseRedirects(urllib.request.HTTPRedirectHandler):
    """Refuse to follow redirects.

    Following a 3xx blindly would replay the request, including the session
    token header, against whatever host the server names.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: N802
        return None


def _build_opener() -> urllib.request.OpenerDirector:
    # ProxyHandler({}) disables proxy discovery. On a managed corporate
    # laptop the environment may define http_proxy, which would route
    # loopback traffic (and the login credentials) through a third party.
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), _RefuseRedirects)


def _encode_path_segment(value: str) -> str:
    """Validate and fully escape a value destined for a URL path segment."""
    if not SAFE_PATH_SEGMENT.match(value or ""):
        raise ErpPermanentError("CLIENT-400", f"unsafe path segment: {value!r}")
    # safe="" so that a slash could never escape the segment.
    return urllib.parse.quote(value, safe="")


# ---------------------------------------------------------------------------
# The client
# ---------------------------------------------------------------------------

class ErpClient:
    """Sequential, self-throttling, self-healing client for the legacy ERP.

    Every single request, authenticated or not, goes through one retry
    engine. Version 1 exempted login and the health check, which meant a
    single rate-limit rejection at the wrong moment aborted the whole run.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        requests_per_second: float = DEFAULT_REQUESTS_PER_SECOND,
        username: str = ERP_USERNAME,
        password: str = ERP_PASSWORD,
        time_budget_seconds: float = DEFAULT_TIME_BUDGET_SECONDS,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        backoff_base_seconds: float = DEFAULT_BACKOFF_BASE_SECONDS,
        backoff_cap_seconds: float = DEFAULT_BACKOFF_CAP_SECONDS,
        rate_limit_cooldown_seconds: float = DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS,
        session_max_uses: int = DEFAULT_SESSION_MAX_USES,
        session_max_age_seconds: float = DEFAULT_SESSION_MAX_AGE_SECONDS,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        clock: "Callable[[], float] | None" = None,
        sleeper: "Callable[[float], None] | None" = None,
        verbose: bool = False,
    ) -> None:
        parsed = urllib.parse.urlsplit(base_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError(f"invalid base URL: {base_url!r}")
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if session_max_uses < 1:
            raise ValueError("session_max_uses must be at least 1")
        if session_max_age_seconds <= 0:
            raise ValueError("session_max_age_seconds must be positive")

        # One clock for every elapsed-time decision this client makes:
        # session age, time budget, backoff and throttling. Real time is the
        # default. Tests pass a fake one so that the 13-minute session expiry
        # and the 250-use limit can be exercised in milliseconds.
        self._clock = clock or time.monotonic
        self._sleep = sleeper or time.sleep

        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.limiter = RateLimiter(requests_per_second, self._clock, self._sleep)
        self.metrics = Metrics()
        self.time_budget_seconds = time_budget_seconds
        self.max_attempts = max_attempts
        self.backoff_base_seconds = backoff_base_seconds
        self.backoff_cap_seconds = backoff_cap_seconds
        self.rate_limit_cooldown_seconds = rate_limit_cooldown_seconds
        self.session_max_uses = session_max_uses
        self.session_max_age_seconds = session_max_age_seconds
        self.max_response_bytes = max_response_bytes
        self.verbose = verbose

        self._opener = _build_opener()
        self._token: "str | None" = None
        self._session_uses = 0
        self._session_started = self._clock()
        # Set while a multi-request operation (a snapshot) is in flight, so
        # that the time budget covers the operation rather than each call.
        self._operation_deadline: "float | None" = None

    # -- logging -----------------------------------------------------------

    def _log(self, message: str) -> None:
        if self.verbose:
            print(f"  . {message}", file=sys.stderr)

    # -- transport ---------------------------------------------------------

    def _send(
        self,
        method: str,
        path: str,
        params: "dict[str, Any] | None" = None,
        form: "dict[str, Any] | None" = None,
        token: "str | None" = None,
    ) -> "tuple[int, bytes, float | None]":
        """Perform exactly one HTTP round trip. Interprets nothing.

        Returns the status, the body, and the `Retry-After` hint in seconds
        if the server sent a usable one.
        """
        url = self.base_url + path
        if params:
            url += "?" + urllib.parse.urlencode(params)

        body = urllib.parse.urlencode(form).encode("utf-8") if form else None
        request = urllib.request.Request(url, data=body, method=method)
        if body is not None:
            request.add_header("Content-Type", "application/x-www-form-urlencoded")
        if token:
            # Header, never query string: the server logs the request line.
            request.add_header("X-ERP-Token", token)

        self.limiter.wait()
        self.metrics.requests += 1
        try:
            with self._opener.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                payload = response.read(self.max_response_bytes + 1)
                if len(payload) > self.max_response_bytes:
                    raise ErpProtocolError(
                        f"response larger than {self.max_response_bytes} bytes from {path}"
                    )
                return response.status, payload, parse_retry_after(
                    response.headers.get("Retry-After")
                )
        except urllib.error.HTTPError as exc:
            # The error body carries the <error><codigo> we dispatch on, and
            # a refused redirect also lands here.
            try:
                payload = exc.read(self.max_response_bytes + 1)
            except (OSError, ValueError):
                payload = b""
            if exc.code in (301, 302, 303, 307, 308):
                raise ErpProtocolError(f"refused redirect ({exc.code}) from {path}") from exc
            return exc.code, payload, parse_retry_after(exc.headers.get("Retry-After"))
        except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as exc:
            raise ErpUnavailable(f"{type(exc).__name__}: {exc}") from exc

    # -- retry helpers -----------------------------------------------------

    def _deadline(self) -> float:
        if self._operation_deadline is not None:
            return self._operation_deadline
        return self._clock() + self.time_budget_seconds

    def _check_budget(self, deadline: float, budget: float) -> None:
        if self._clock() > deadline:
            raise ErpUnavailable(f"time budget of {budget:.0f}s exhausted")

    def _backoff(self, attempt: int, reason: str) -> None:
        delay = min(self.backoff_base_seconds * (2 ** (attempt - 1)), self.backoff_cap_seconds)
        self._log(f"{reason}; retrying in {delay:.2f}s")
        self._sleep(delay)

    def _rate_limit_cooldown(self, retry_after: "float | None") -> float:
        """How long to stay off the wire after an ERP-429.

        Our own cooldown is a floor, not a default: the server currently
        says `Retry-After: 1`, and obeying that literally would put us back
        on the wire while its sliding window is still full. If the server
        ever asks for longer, it knows something we do not, so we obey.
        `parse_retry_after` has already capped the value.
        """
        if retry_after is None:
            return self.rate_limit_cooldown_seconds
        return max(self.rate_limit_cooldown_seconds, retry_after)

    # -- session -----------------------------------------------------------

    @property
    def session_expired(self) -> bool:
        if self._token is None:
            return True
        if self._session_uses >= self.session_max_uses:
            return True
        return (self._clock() - self._session_started) >= self.session_max_age_seconds

    def _login_once(self) -> "tuple[bool, str, str, float | None]":
        """One login attempt.

        Returns (ok, error_code, error_message, retry_after_seconds).
        """
        status, body, retry_after = self._send(
            "POST", "/erp/login", form={"usuario": self.username, "clave": self.password}
        )
        if status != 200:
            return False, _error_code(body) or str(status), _error_message(body), retry_after

        root = _parse_xml(body, "login")
        token = _element_text(root.find("token"))
        if not token:
            raise ErpProtocolError("login succeeded but returned no token")

        self._token = token
        self._session_uses = 0
        self._session_started = self._clock()
        self.metrics.logins += 1
        self.metrics.successful_responses += 1
        self._log("authenticated, new session established")
        return True, "", "", None

    def ensure_session(self, deadline: "float | None" = None) -> None:
        """Establish a session if there is none, or if ours is about to die.

        Renewal is proactive: waiting for SES-401 would work but wastes a
        round trip and muddies the metrics.
        """
        if not self.session_expired:
            return
        if deadline is None:
            deadline = self._deadline()

        last_error = "no attempt made"
        for attempt in range(1, self.max_attempts + 1):
            self._check_budget(deadline, self.time_budget_seconds)
            try:
                ok, code, message, retry_after = self._login_once()
            except ErpUnavailable as exc:
                self.metrics.retries_network += 1
                last_error = str(exc)
                self._backoff(attempt, f"network failure during login ({exc})")
                continue
            except ErpProtocolError as exc:
                self.metrics.retries_protocol += 1
                last_error = str(exc)
                self._backoff(attempt, f"protocol failure during login ({exc})")
                continue

            if ok:
                return

            if code == "ERP-429":
                # The rate limiter is checked before routing, so even the
                # login endpoint can be throttled.
                cooldown = self._rate_limit_cooldown(retry_after)
                self.metrics.retries_rate_limited += 1
                self.limiter.penalize(cooldown)
                last_error = f"{code}: {message}"
                self._log(f"rate limited during login, cooling down {cooldown:.2f}s")
                continue

            # Wrong credentials, unknown endpoint: retrying cannot help.
            raise ErpPermanentError(code, message)

        raise ErpUnavailable(
            f"could not authenticate after {self.max_attempts} attempts: {last_error}"
        )

    # -- the single retry engine -------------------------------------------

    def _get(
        self,
        path: str,
        params: "dict[str, Any] | None" = None,
        authenticated: bool = True,
        parse: "Callable[[bytes], T] | None" = None,
    ) -> Any:
        """Perform a GET, absorbing every transient failure mode.

        The response parser runs *inside* the retry loop on purpose: a
        truncated body or a missing element is a transport symptom, and the
        next attempt usually succeeds. Version 1 parsed outside the loop, so
        one dropped connection killed a 26-page dump.
        """
        deadline = self._deadline()
        last_error = "no attempt made"

        for attempt in range(1, self.max_attempts + 1):
            self._check_budget(deadline, self.time_budget_seconds)

            token = None
            if authenticated:
                self.ensure_session(deadline)
                token = self._token

            try:
                status, body, retry_after = self._send(
                    "GET", path, params=params, token=token
                )
            except ErpUnavailable as exc:
                self.metrics.retries_network += 1
                last_error = str(exc)
                self._backoff(attempt, f"network failure on {path} ({exc})")
                continue
            except ErpProtocolError as exc:
                self.metrics.retries_protocol += 1
                last_error = str(exc)
                self._backoff(attempt, f"protocol failure on {path} ({exc})")
                continue

            if status == 200:
                # The server has already spent a session use by this point,
                # whether or not we manage to read the body.
                if authenticated:
                    self._session_uses += 1
                if parse is None:
                    self.metrics.successful_responses += 1
                    return body
                try:
                    result = parse(body)
                except ErpProtocolError as exc:
                    self.metrics.retries_protocol += 1
                    last_error = str(exc)
                    self._backoff(attempt, f"unreadable response from {path} ({exc})")
                    continue
                self.metrics.successful_responses += 1
                return result

            code = _error_code(body)
            message = _error_message(body)
            last_error = f"{code or status}: {message}"

            if code == "ORA-00600":
                # Injected fault. It is evaluated after session validation,
                # so it does consume a session use. Two multiples of ten are
                # never consecutive, so an immediate retry always succeeds
                # for a single sequential client; no backoff needed.
                if authenticated:
                    self._session_uses += 1
                self.metrics.retries_ora00600 += 1
                self._log(f"ORA-00600 on {path} {params or ''}; retrying immediately")
                continue

            if code == "ERP-429":
                # Rejected requests are also recorded in the server's window,
                # so the whole window must drain before we try again. The
                # server tells us how long in Retry-After; we never wait less
                # than our own floor, and never more than the cap.
                cooldown = self._rate_limit_cooldown(retry_after)
                self.metrics.retries_rate_limited += 1
                self.limiter.penalize(cooldown)
                self._log(f"ERP-429 on {path}; cooling down {cooldown:.2f}s")
                continue

            if code == "SES-401":
                # Does not consume a session use: the server returns before
                # incrementing. Drop the token and re-authenticate.
                self.metrics.retries_session_expired += 1
                self._token = None
                self._log(f"SES-401 on {path}; re-authenticating")
                continue

            # ERP-400, ERP-404, anything unknown: our fault, not transient.
            raise ErpPermanentError(code or str(status), message, status)

        raise ErpUnavailable(
            f"exhausted {self.max_attempts} attempts on {path}; last error: {last_error}"
        )

    # -- endpoints ---------------------------------------------------------

    def status(self) -> "dict[str, Any]":
        """Read /erp/estado. Anonymous, and it does not touch the ORA-00600
        counter, which makes it the cheapest possible health check. It does
        still count against the rate limit."""

        def _parse(body: bytes) -> "dict[str, Any]":
            root = _parse_xml(body, "/erp/estado")
            if root.tag != "estado":
                raise ErpProtocolError(f"/erp/estado: unexpected root <{root.tag}>")
            return {
                "version": _element_text(root.find("version")),
                "uptime_seconds": _safe_int(root.find("activo_segundos")),
                "entry_count": _safe_int(root.find("asientos")),
                "update_loaded": _element_text(root.find("actualizacion_cargada")) == "SI",
            }

        return self._get("/erp/estado", authenticated=False, parse=_parse)

    def page(self, number: int) -> "tuple[dict[str, int], list[Entry]]":
        if number < 1:
            raise ErpPermanentError("CLIENT-400", f"page numbers start at 1, got {number}")

        def _parse(body: bytes) -> "tuple[dict[str, int], list[Entry]]":
            context = f"/erp/asientos?pagina={number}"
            root = _parse_xml(body, context)
            meta_node = root.find("meta")
            if meta_node is None:
                raise ErpProtocolError(f"{context}: response has no <meta> block")
            meta = {
                "total": _safe_int(meta_node.find("total")),
                "pages": _safe_int(meta_node.find("paginas"), default=1),
                "page": _safe_int(meta_node.find("pagina"), default=number),
                "page_size": _safe_int(meta_node.find("por_pagina"), default=20),
            }
            entries = [Entry.from_xml(node) for node in root.iterfind("./asientos/asiento")]
            return meta, entries

        return self._get("/erp/asientos", {"pagina": number}, parse=_parse)

    def entry(self, entry_id: str) -> "Entry | None":
        """Fetch a single entry, or None if the ERP does not know it."""
        path = "/erp/asientos/" + _encode_path_segment(entry_id)

        def _parse(body: bytes) -> "Entry | None":
            root = _parse_xml(body, path)
            node = root.find("./asientos/asiento")
            return Entry.from_xml(node) if node is not None else None

        try:
            return self._get(path, parse=_parse)
        except ErpPermanentError as exc:
            if exc.code == "ERP-404":
                return None
            raise

    def snapshot(self) -> Snapshot:
        """Download every entry and wrap it in a self-describing snapshot.

        Reads /erp/estado before and after so that a mid-flight data reload
        (the Saturday batch) is detected rather than silently mixed in.
        """
        started = self._clock()
        self._operation_deadline = started + self.time_budget_seconds
        try:
            status_before = self.status()
            meta, entries = self.page(1)
            total_pages = max(1, meta["pages"])
            self._log(f"{meta['total']} entries across {total_pages} pages")

            for number in range(2, total_pages + 1):
                _, chunk = self.page(number)
                entries.extend(chunk)

            status_after = self.status()
        finally:
            self._operation_deadline = None

        self.metrics.elapsed_seconds = self._clock() - started
        diagnostics = build_diagnostics(entries, meta["total"], status_before, status_after)
        return Snapshot(
            entries=entries,
            fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            erp_status_before=status_before,
            erp_status_after=status_after,
            diagnostics=diagnostics,
            metrics=self.metrics,
        )


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_jsonl_atomically(entries: "Sequence[Entry]", destination: Path) -> None:
    """Write the snapshot so that readers never observe a partial file.

    A crash halfway through a plain write leaves a truncated JSONL that
    still looks syntactically valid, and the next consumer would silently
    process a subset. Writing to a temporary file in the same directory and
    then renaming makes the swap atomic on POSIX.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(destination.parent),
        prefix=destination.name + ".",
        suffix=".tmp",
        delete=False,
    )
    temporary = Path(handle.name)
    try:
        with handle:
            for entry in entries:
                handle.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def command_status(client: ErpClient, args: argparse.Namespace) -> int:
    print(json.dumps(client.status(), indent=2, ensure_ascii=False))
    return 0


def command_dump(client: ErpClient, args: argparse.Namespace) -> int:
    snapshot = client.snapshot()

    output = Path(args.output)
    write_jsonl_atomically(snapshot.entries, output)

    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(snapshot.report(), indent=2, ensure_ascii=False), encoding="utf-8"
        )

    diagnostics = snapshot.diagnostics
    print(f"written   : {output}", file=sys.stderr)
    print(f"entries   : {diagnostics['received_total']} of {diagnostics['declared_total']}",
          file=sys.stderr)
    print(f"metrics   : {snapshot.metrics.summary()}", file=sys.stderr)
    print(f"diagnostic: {json.dumps(diagnostics, ensure_ascii=False)}", file=sys.stderr)

    failed = False
    if diagnostics["snapshot_drift"]:
        print("FAIL: the ERP changed mid-dump. Re-run against a stable ERP.", file=sys.stderr)
        failed = True
    elif not diagnostics["complete"]:
        print("FAIL: snapshot is not complete; downstream stages must not run.", file=sys.stderr)
        failed = True

    if diagnostics["duplicate_entry_ids"]:
        print(f"WARN: duplicate entry ids: {diagnostics['duplicate_entry_ids']}", file=sys.stderr)
    if diagnostics["duplicate_order_ids"]:
        print(f"WARN: duplicate order ids: {diagnostics['duplicate_order_ids']}", file=sys.stderr)
    if diagnostics["missing_entry_ids"]:
        print(
            f"WARN: {len(diagnostics['missing_entry_ids'])} entry ids missing from their "
            f"series: {diagnostics['missing_entry_ids']}",
            file=sys.stderr,
        )
    return 1 if failed else 0


def command_probe(client: ErpClient, args: argparse.Namespace) -> int:
    """Measure where the injected faults land. Useful as evidence, and as a
    regression check that the retry policy really is transparent."""
    print(f"Requesting page 1 {args.count} times and recording what happens.\n", file=sys.stderr)
    client.ensure_session()
    failures = []
    for index in range(1, args.count + 1):
        before = client.metrics.retries_ora00600
        client.page(1)
        if client.metrics.retries_ora00600 > before:
            failures.append(index)
            print(f"  query {index:3d}  ORA-00600, recovered on retry", file=sys.stderr)
        else:
            print(f"  query {index:3d}  ok", file=sys.stderr)
    print(f"\nfaults at queries: {failures}", file=sys.stderr)
    print(f"metrics: {client.metrics.summary()}", file=sys.stderr)
    return 0


def command_selftest(client: ErpClient, args: argparse.Namespace) -> int:
    """Offline checks of the pure functions. Requires no ERP."""
    cases: "list[tuple[str, Callable[[], Any], Any]]" = [
        ("amount spanish grouped", lambda: parse_legacy_amount("12.874,40")[0], Decimal("12874.40")),
        ("amount spanish plain", lambda: parse_legacy_amount("524,98")[0], Decimal("524.98")),
        ("amount english decimal", lambda: parse_legacy_amount("1234.56")[0], Decimal("1234.56")),
        ("amount english cents", lambda: parse_legacy_amount("0.99")[0], Decimal("0.99")),
        ("amount integer", lambda: parse_legacy_amount("1234")[0], Decimal("1234")),
        ("amount negative", lambda: parse_legacy_amount("-12.874,40")[0], Decimal("-12874.40")),
        ("amount malformed groups", lambda: parse_legacy_amount("12,34,56")[0], None),
        ("amount double separator", lambda: parse_legacy_amount("1..2")[0], None),
        ("amount garbage", lambda: parse_legacy_amount("N/A")[0], None),
        ("amount empty", lambda: parse_legacy_amount("")[0], None),
        ("date legacy", lambda: parse_legacy_date("21/03/2026")[0], date(2026, 3, 21)),
        ("date iso fallback", lambda: parse_legacy_date("2026-03-21")[0], date(2026, 3, 21)),
        ("date garbage", lambda: parse_legacy_date("31/02/2026")[0], None),
        ("gaps", lambda: find_id_gaps(["AS-00001", "AS-00003"]), ["AS-00002"]),
        ("gaps across series", lambda: find_id_gaps(["AS-00518", "AS-70001"]), []),
    ]
    failures = 0
    for name, run, expected in cases:
        actual = run()
        ok = actual == expected
        failures += 0 if ok else 1
        print(f"  {'PASS' if ok else 'FAIL'}  {name}: {actual!r}"
              + ("" if ok else f" (expected {expected!r})"))
    print(f"\n{len(cases) - failures}/{len(cases)} checks passed")
    return 0 if failures == 0 else 1


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    # Shared options live in a parent parser so that they work both before
    # and after the sub-command, which is what users actually type.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--base-url", default=DEFAULT_BASE_URL,
                        help=f"ERP base URL (default: {DEFAULT_BASE_URL})")
    common.add_argument("--rps", type=float, default=DEFAULT_REQUESTS_PER_SECOND,
                        help="client-side request rate; the server rejects above 10")
    common.add_argument("--time-budget", type=float, default=DEFAULT_TIME_BUDGET_SECONDS,
                        help="abort the whole operation after this many seconds")
    common.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS,
                        help="retries per request before giving up")
    common.add_argument("-v", "--verbose", action="store_true")

    parser = argparse.ArgumentParser(
        prog="erp_client",
        description="Hardened client for the legacy ERP Miralmar 2009 bridge",
        parents=[common],
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status", parents=[common],
                                   help="cheap health check: version, entry count, batch flag")
    status.set_defaults(handler=command_status)

    dump = subparsers.add_parser("dump", parents=[common],
                                 help="download every entry into a JSONL snapshot")
    dump.add_argument("--output", default="data/erp_entries.jsonl")
    dump.add_argument("--report", default=None, help="also write a JSON run report here")
    dump.set_defaults(handler=command_dump)

    probe = subparsers.add_parser("probe", parents=[common],
                                  help="measure where the injected ORA-00600 faults land")
    probe.add_argument("--count", type=int, default=25)
    probe.set_defaults(handler=command_probe)

    selftest = subparsers.add_parser("selftest", parents=[common],
                                     help="offline checks of the parsers; no ERP required")
    selftest.set_defaults(handler=command_selftest)

    return parser


def main(argv: "Sequence[str] | None" = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        client = ErpClient(
            base_url=args.base_url,
            requests_per_second=args.rps,
            time_budget_seconds=args.time_budget,
            max_attempts=args.max_attempts,
            verbose=args.verbose,
        )
    except ValueError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return 4

    try:
        return int(args.handler(client, args))
    except ErpUnavailable as exc:
        print(f"\nERROR: the ERP is unreachable.\n  {exc}", file=sys.stderr)
        print("  Start it with:  cd 500-sombras-de-alberto && make erp", file=sys.stderr)
        return 2
    except (ErpPermanentError, ErpProtocolError) as exc:
        print(f"\nERROR: the ERP rejected the request.\n  {exc}", file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
