#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Resolve an OCR-extracted invoice to an ERP entry.

The purchase order code is the natural join key, but it cannot be relied upon:
it may be absent from the document, mangled by OCR, or simply wrong. This
module turns "look up the order id" into a cascade of progressively weaker
strategies, each of which reports how it got there so the caller can decide
whether to trust it.

Two rules shape the whole design.

1. The resolver never guesses silently. Every result carries the strategy that
   produced it and a confidence level. Anything below EXACT is a candidate for
   human review, not an answer.

2. The invoice date anchors the search and the amount only breaks ties. The
   amount is the thing being audited, so it must not become the thing being
   searched on: an invoice whose amount was tampered with has to remain
   findable, otherwise the tampering is undetectable.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import Iterable, Mapping, Sequence

__all__ = [
    "BLOCKING_ANOMALIES",
    "Confidence",
    "Strategy",
    "Anomaly",
    "Entry",
    "InvoiceSignals",
    "Resolution",
    "ErpIndex",
    "OrderResolver",
    "normalise_amount",
    "normalise_date",
    "repair_order_code",
    "find_order_codes",
]

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

#: The bank receiving every invoice. Its tax id appears on all documents and
#: must never be mistaken for the supplier's.
CLIENT_TAX_ID = "A58231074"

#: The only shape a purchase order takes in this dataset. Verified against all
#: 516 ERP entries and all 471 invoices that carry a text layer.
ORDER_CODE = re.compile(r"\bPO-(\d{4})-(\d{4})\b")

#: Deliberately permissive: catches separators and digit/letter confusions that
#: OCR introduces. Only used to *propose* a repair, never as a direct match.
ORDER_CODE_LOOSE = re.compile(
    r"\bP[O0Q]\s*[-–—_. ]?\s*([0-9OQlIiSsBbZz]{4})\s*[-–—_. ]?\s*([0-9OQlIiSsBbZz]{1,4})\b"
)

#: Characters OCR habitually swaps for digits.
GLYPH_TO_DIGIT = str.maketrans({
    "O": "0", "o": "0", "Q": "0", "D": "0",
    "l": "1", "I": "1", "i": "1", "|": "1",
    "S": "5", "s": "5",
    "B": "8",
    "Z": "2", "z": "2",
    "G": "6",
    "T": "7",
})

SPANISH_MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}

TAX_ID = re.compile(r"\b([A-HJ-NP-SUVW]\d{8}|\d{8}[A-Z]|[XYZ]\d{7}[A-Z])\b")

_AMOUNT_ES_GROUPED = re.compile(r"^\d{1,3}(\.\d{3})+,\d{1,2}$")
_AMOUNT_ES_PLAIN = re.compile(r"^\d+,\d{1,2}$")
_AMOUNT_EN_GROUPED = re.compile(r"^\d{1,3}(,\d{3})+\.\d{1,2}$")
_AMOUNT_EN_PLAIN = re.compile(r"^\d+(\.\d{1,2})?$")
_AMOUNT_INTEGER = re.compile(r"^\d+$")

_DATE_NUMERIC = re.compile(r"\b(\d{1,2})\s*[/.\-]\s*(\d{1,2})\s*[/.\-]\s*(\d{4})\b")
_DATE_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DATE_WORDS = re.compile(
    r"\b(\d{1,2})\s+de\s+([A-Za-zÁ-Úá-ú]+)\s+de\s+(\d{4})\b", re.IGNORECASE)


# --------------------------------------------------------------------------
# Vocabulary
# --------------------------------------------------------------------------

class Confidence(str, Enum):
    """How much weight the caller may put on a resolution."""

    EXACT = "exact"      # the document stated the order and the ERP knows it
    HIGH = "high"        # reconstructed from strong, mutually consistent signals
    MEDIUM = "medium"    # a single plausible candidate, but on a weaker key
    LOW = "low"          # a candidate exists but the evidence is thin
    NONE = "none"        # no answer


class Strategy(str, Enum):
    """Which rung of the ladder produced the answer."""

    ORDER_CODE = "order_code"
    ORDER_CODE_REPAIRED = "order_code_repaired"
    NIF_AND_DATE = "nif_and_date"
    NIF_AND_AMOUNT = "nif_and_amount"
    AMOUNT_ONLY = "amount_only"
    NONE = "none"


class Anomaly(str, Enum):
    """Everything worth telling a human about, whatever the outcome."""

    NO_ORDER_CODE = "no_order_code"
    ORDER_CODE_REPAIRED = "order_code_repaired"
    ORDER_CODE_UNKNOWN_TO_ERP = "order_code_unknown_to_erp"
    MULTIPLE_ORDER_CODES = "multiple_order_codes"
    DUPLICATE_ORDER_IN_ERP = "duplicate_order_in_erp"
    SUPPLIER_TAX_ID_MISMATCH = "supplier_tax_id_mismatch"
    SUPPLIER_TAX_ID_MISSING = "supplier_tax_id_missing"
    ENTRY_TAX_ID_MISSING = "entry_tax_id_missing"
    INVOICE_DATE_UNPARSEABLE = "invoice_date_unparseable"
    INVOICE_DATE_IMPOSSIBLE = "invoice_date_impossible"
    DATE_MISMATCH = "date_mismatch"
    AMOUNT_MISMATCH = "amount_mismatch"
    AMOUNT_UNPARSEABLE = "amount_unparseable"
    AMBIGUOUS_CANDIDATES = "ambiguous_candidates"
    RESOLVED_WITHOUT_ORDER_CODE = "resolved_without_order_code"
    ENTRY_ALREADY_PAID = "entry_already_paid"
    ENTRY_HAS_WARNINGS = "entry_has_warnings"


#: Anomalies that should stop a payment outright rather than merely annotate
#: it. The rest are context a reviewer may reasonably wave through; these are
#: not. Paying twice, paying the wrong supplier, or paying against an order the
#: ledger cannot pin down are all unrecoverable once the money has moved.
BLOCKING_ANOMALIES = frozenset({
    Anomaly.ENTRY_ALREADY_PAID.value,
    Anomaly.DUPLICATE_ORDER_IN_ERP.value,
    Anomaly.SUPPLIER_TAX_ID_MISMATCH.value,
    Anomaly.ORDER_CODE_UNKNOWN_TO_ERP.value,
    Anomaly.INVOICE_DATE_IMPOSSIBLE.value,
})


# --------------------------------------------------------------------------
# Normalisation
# --------------------------------------------------------------------------

def normalise_amount(raw) -> int | None:
    """Return an amount in cents, or None if the input is not a bare amount.

    Handles both conventions seen in the corpus: Spanish ``1.250,00`` and
    English ``3400.00``. Working in integer cents keeps equality meaningful;
    comparing floats for money invites rounding bugs that look like fraud.

    The input must be an amount and nothing else, aside from currency markers.
    Anything carrying other text is rejected rather than mined for digits.
    An earlier version stripped every non-digit character first, which turned
    ``"IVA (21%): 295,97"`` into 21.295,97 and ``"30 dias fecha factura"``
    into 30,00. A field that holds a sentence is a broken field, and saying so
    is the only safe answer.
    """
    if raw is None:
        return None
    if isinstance(raw, int) and not isinstance(raw, bool):
        return raw * 100
    if isinstance(raw, float):
        return int(round(raw * 100))

    text = str(raw).replace("\u00a0", " ").replace("\u202f", " ").strip()
    if not text:
        return None

    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative, text = True, text[1:-1].strip()

    # Currency markers may sit on either side; nothing else may.
    text = re.sub(r"(?i)^(eur|euros?|usd|€|\$)\s*", "", text)
    text = re.sub(r"(?i)\s*(eur|euros?|usd|€|\$)$", "", text)
    text = text.strip()

    if text.startswith("-"):
        negative, text = True, text[1:].strip()
    elif text.startswith("+"):
        text = text[1:].strip()

    # No internal whitespace, no letters, no stray punctuation. The remainder
    # has to be the number itself.
    text = text.replace(" ", "")
    if not text or not re.fullmatch(r"[\d.,]+", text):
        return None

    if _AMOUNT_ES_GROUPED.match(text):
        digits = text.replace(".", "").replace(",", ".")
    elif _AMOUNT_ES_PLAIN.match(text):
        digits = text.replace(",", ".")
    elif _AMOUNT_EN_GROUPED.match(text):
        digits = text.replace(",", "")
    elif _AMOUNT_EN_PLAIN.match(text):
        digits = text
    elif _AMOUNT_INTEGER.match(text):
        digits = text
    else:
        # Ambiguous shapes such as "1,234" could be either convention. Refusing
        # to choose is safer than silently picking the wrong order of magnitude.
        return None

    try:
        value = float(digits)
    except ValueError:
        return None
    cents = int(round(value * 100))
    return -cents if negative else cents


def normalise_date(raw) -> tuple[date | None, str | None]:
    """Return ``(date, anomaly)``.

    A calendar-impossible date such as ``31/02/2026`` is reported distinctly
    from an unreadable one: the first is a forgery signal, the second is an
    extraction problem. Conflating them loses the signal.
    """
    if raw is None:
        return None, Anomaly.INVOICE_DATE_UNPARSEABLE.value
    if isinstance(raw, date):
        return raw, None

    text = str(raw).strip()
    if not text:
        return None, Anomaly.INVOICE_DATE_UNPARSEABLE.value

    match = _DATE_ISO.search(text)
    if match:
        year, month, day = (int(x) for x in match.groups())
        return _build_date(year, month, day)

    match = _DATE_NUMERIC.search(text)
    if match:
        day, month, year = (int(x) for x in match.groups())
        return _build_date(year, month, day)

    match = _DATE_WORDS.search(text)
    if match:
        day, word, year = match.group(1), match.group(2), match.group(3)
        key = _strip_accents(word).lower()
        month = SPANISH_MONTHS.get(key)
        if month:
            return _build_date(int(year), month, int(day))

    return None, Anomaly.INVOICE_DATE_UNPARSEABLE.value


def _build_date(year: int, month: int, day: int) -> tuple[date | None, str | None]:
    try:
        return date(year, month, day), None
    except ValueError:
        return None, Anomaly.INVOICE_DATE_IMPOSSIBLE.value


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text)
                   if unicodedata.category(c) != "Mn")


def normalise_tax_id(raw) -> str:
    if not raw:
        return ""
    return re.sub(r"[^A-Z0-9]", "", str(raw).upper())


def normalise_name(raw) -> str:
    """Casefold, drop accents and legal suffixes so names can be compared."""
    if not raw:
        return ""
    text = _strip_accents(str(raw)).upper()
    text = re.sub(r"[^A-Z0-9 ]", " ", text)
    text = re.sub(r"\b(S L U?|S A U?|S C|S COOP|SL|SA|SLU|SAU|SC)\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def find_order_codes(text: str) -> list[str]:
    """Every canonical order code in the text, deduplicated, order preserved.

    Multi-page invoices repeat the code in the header of each page, so
    duplicates are expected and harmless. Two *different* codes are not.
    """
    seen: list[str] = []
    for match in ORDER_CODE.finditer(text or ""):
        code = match.group(0)
        if code not in seen:
            seen.append(code)
    return seen


def repair_order_code(text: str) -> list[str]:
    """Propose canonical codes from near-misses left by OCR.

    Returns candidates only; the caller must confirm each against the ERP.
    A repair that does not correspond to a real order is discarded rather than
    reported, because an invented order number is worse than none at all.
    """
    proposals: list[str] = []
    for match in ORDER_CODE_LOOSE.finditer(text or ""):
        year = match.group(1).translate(GLYPH_TO_DIGIT)
        number = match.group(2).translate(GLYPH_TO_DIGIT)
        if not year.isdigit() or not number.isdigit():
            continue
        if len(number) > 4:
            continue
        code = f"PO-{year}-{int(number):04d}"
        if ORDER_CODE.fullmatch(code) and code not in proposals:
            proposals.append(code)
    return proposals


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Entry:
    """One ERP accounting entry, normalised."""

    entry_id: str
    order_id: str
    supplier_id: str
    tax_id: str
    status: str
    date: date | None
    amount_cents: int | None
    raw_date: str = ""
    raw_amount: str = ""
    warnings: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: Mapping) -> "Entry":
        parsed_date, _ = normalise_date(data.get("date") or data.get("raw_date"))
        amount = normalise_amount(data.get("amount"))
        if amount is None:
            amount = normalise_amount(data.get("raw_amount"))
        return cls(
            entry_id=str(data.get("entry_id") or ""),
            order_id=str(data.get("order_id") or ""),
            supplier_id=str(data.get("supplier_id") or ""),
            tax_id=normalise_tax_id(data.get("tax_id")),
            status=str(data.get("status") or ""),
            date=parsed_date,
            amount_cents=amount,
            raw_date=str(data.get("raw_date") or ""),
            raw_amount=str(data.get("raw_amount") or ""),
            warnings=tuple(data.get("warnings") or ()),
        )


@dataclass
class InvoiceSignals:
    """What the resolver needs from the extraction layer.

    Deliberately a superset of nothing: every field is optional, because the
    whole point is to cope with documents that are missing some of them. The
    field names mirror ``InvoiceFeatures`` so the two can be adapted trivially.
    """

    purchase_order: str | None = None
    supplier_nif: str | None = None
    supplier_name: str | None = None
    invoice_date: str | date | None = None
    total: str | float | None = None
    tax_base: str | float | None = None
    invoice_number: str | None = None
    iban: str | None = None
    raw_text: str = ""
    source_name: str = ""

    @classmethod
    def from_features(cls, features, raw_text: str = "", source_name: str = "") -> "InvoiceSignals":
        """Adapt a backend ``InvoiceFeatures`` object or plain mapping."""
        get = features.get if isinstance(features, Mapping) else \
            (lambda key, default=None: getattr(features, key, default))
        return cls(
            purchase_order=get("purchase_order"),
            supplier_nif=get("supplier_nif"),
            supplier_name=get("supplier_name"),
            invoice_date=get("invoice_date"),
            total=get("total"),
            tax_base=get("tax_base"),
            invoice_number=get("invoice_number"),
            iban=get("iban"),
            raw_text=raw_text,
            source_name=source_name,
        )


@dataclass
class Resolution:
    """The outcome, plus everything needed to justify or contest it."""

    entry: Entry | None
    strategy: Strategy
    confidence: Confidence
    candidates: tuple[Entry, ...] = ()
    anomalies: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    @property
    def order_id(self) -> str | None:
        return self.entry.order_id if self.entry else None

    @property
    def resolved(self) -> bool:
        return self.entry is not None

    @property
    def needs_review(self) -> bool:
        """True when a human must look at it before any payment decision.

        Note what this is not: it is not "did we find the entry". A perfectly
        resolved invoice whose entry is already PAGADA is the most dangerous
        document in the batch, and it resolves by exact order code with full
        confidence. Any anomaly at all therefore forces review.

        The only way through without review is an exact order code whose
        corroboration came back completely clean.
        """
        return (
            not self.resolved
            or self.confidence is not Confidence.EXACT
            or self.strategy is not Strategy.ORDER_CODE
            or bool(self.anomalies)
        )

    @property
    def blocking_anomalies(self) -> tuple[str, ...]:
        """Anomalies that should stop a payment outright, not merely flag it."""
        return tuple(a for a in self.anomalies if a in BLOCKING_ANOMALIES)

    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id,
            "entry_id": self.entry.entry_id if self.entry else None,
            "strategy": self.strategy.value,
            "confidence": self.confidence.value,
            "resolved": self.resolved,
            "needs_review": self.needs_review,
            "candidates": [c.order_id for c in self.candidates],
            "candidate_entry_ids": [c.entry_id for c in self.candidates],
            "anomalies": list(self.anomalies),
            "blocking_anomalies": list(self.blocking_anomalies),
            "notes": list(self.notes),
        }


# --------------------------------------------------------------------------
# Index
# --------------------------------------------------------------------------

class ErpIndex:
    """In-memory indexes over the ERP snapshot.

    Built once, queried many times. Every lookup the resolver needs is O(1) or
    O(size of a small bucket), so the cascade stays cheap even when it has to
    try every rung.
    """

    def __init__(self, entries: Iterable[Mapping | Entry]):
        grouped: dict[str, list[Entry]] = {}
        self._all: list[Entry] = []

        for item in entries:
            entry = item if isinstance(item, Entry) else Entry.from_dict(item)
            if not entry.order_id:
                continue
            grouped.setdefault(entry.order_id, []).append(entry)
            self._all.append(entry)

        self._grouped = grouped
        self.duplicate_order_ids = sorted(o for o, rows in grouped.items() if len(rows) > 1)
        self._duplicated = frozenset(self.duplicate_order_ids)

        # Only orders backed by exactly one row are directly addressable. A
        # duplicated order is not a row we may choose between; it is a defect
        # in the ledger, and choosing would hide it.
        self._by_order = {o: rows[0] for o, rows in grouped.items() if len(rows) == 1}

        self._by_nif_date: dict[tuple[str, date], list[Entry]] = {}
        self._by_nif_amount: dict[tuple[str, int], list[Entry]] = {}
        self._by_amount: dict[int, list[Entry]] = {}
        self._by_nif: dict[str, list[Entry]] = {}

        # The secondary indexes span every row, duplicates included, so a
        # fallback search surfaces them as competing candidates instead of
        # quietly missing one.
        for entry in self._all:
            if entry.tax_id:
                self._by_nif.setdefault(entry.tax_id, []).append(entry)
                if entry.date:
                    self._by_nif_date.setdefault((entry.tax_id, entry.date), []).append(entry)
                if entry.amount_cents is not None:
                    self._by_nif_amount.setdefault((entry.tax_id, entry.amount_cents), []).append(entry)
            if entry.amount_cents is not None:
                self._by_amount.setdefault(entry.amount_cents, []).append(entry)

    @classmethod
    def from_jsonl(cls, path) -> "ErpIndex":
        """Build the index straight from the file erp_client writes.

        This is the whole integration surface: there is no service to call and
        nothing to keep running. The dumper produces a file, the consumer reads
        it. If the file is missing the caller gets FileNotFoundError at startup,
        which is the right moment to find out.
        """
        import json
        from pathlib import Path

        text = Path(path).read_text(encoding="utf-8")
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
        if not rows:
            raise ValueError(f"ERP snapshot at {path} is empty")
        return cls(rows)

    def __len__(self) -> int:
        """Number of distinct order ids, duplicated ones counted once."""
        return len(self._grouped)

    @property
    def entries(self) -> Sequence[Entry]:
        return tuple(self._all)

    def is_duplicated(self, order_id: str) -> bool:
        return order_id in self._duplicated

    def known_order(self, order_id: str) -> bool:
        """True if the ERP has the order at all, however many rows it has."""
        return order_id in self._grouped

    def rows_for_order(self, order_id: str) -> list[Entry]:
        """Every row carrying this order id. More than one is a defect."""
        return list(self._grouped.get(order_id, ()))

    def by_order(self, order_id: str) -> Entry | None:
        """The single row for this order, or None if there is not exactly one.

        Returns None for a duplicated order on purpose. Callers must consult
        ``is_duplicated`` to tell "unknown" from "ambiguous"; conflating them
        would report a ledger defect as a missing order.
        """
        return self._by_order.get(order_id)

    def by_nif_and_date(self, tax_id: str, day: date, window_days: int = 0) -> list[Entry]:
        if window_days == 0:
            return list(self._by_nif_date.get((tax_id, day), ()))
        found: list[Entry] = []
        for offset in range(-window_days, window_days + 1):
            found.extend(self._by_nif_date.get((tax_id, day + timedelta(days=offset)), ()))
        return found

    def by_nif_and_amount(self, tax_id: str, amount_cents: int) -> list[Entry]:
        return list(self._by_nif_amount.get((tax_id, amount_cents), ()))

    def by_amount(self, amount_cents: int) -> list[Entry]:
        return list(self._by_amount.get(amount_cents, ()))

    def by_nif(self, tax_id: str) -> list[Entry]:
        return list(self._by_nif.get(tax_id, ()))


# --------------------------------------------------------------------------
# Resolver
# --------------------------------------------------------------------------

class OrderResolver:
    """Map an invoice onto an ERP entry, or explain why it cannot be done."""

    def __init__(
        self,
        index: ErpIndex,
        *,
        date_window_days: int = 0,
        allow_amount_only: bool = True,
        repair_order_codes: bool = True,
    ):
        self.index = index
        self.date_window_days = date_window_days
        self.allow_amount_only = allow_amount_only
        self.repair_order_codes = repair_order_codes

    # -- public ------------------------------------------------------------

    def resolve(self, signals: InvoiceSignals) -> Resolution:
        anomalies: list[str] = []
        notes: list[str] = []

        tax_id = normalise_tax_id(signals.supplier_nif)
        if tax_id == CLIENT_TAX_ID:
            # The payer's own tax id was mistaken for the supplier's.
            notes.append("supplier_nif held the client tax id; ignored")
            tax_id = ""
        if not tax_id:
            tax_id = self._tax_id_from_text(signals.raw_text)
            if tax_id:
                notes.append("supplier tax id recovered from raw text")
        if not tax_id:
            anomalies.append(Anomaly.SUPPLIER_TAX_ID_MISSING.value)

        invoice_date, date_anomaly = normalise_date(signals.invoice_date)
        if date_anomaly:
            anomalies.append(date_anomaly)

        total_cents = normalise_amount(signals.total)
        if total_cents is None and signals.total is not None:
            anomalies.append(Anomaly.AMOUNT_UNPARSEABLE.value)

        for attempt in (
            self._by_stated_code,
            self._by_repaired_code,
            self._by_nif_and_date,
            self._by_nif_and_amount,
            self._by_amount_only,
        ):
            result = attempt(signals, tax_id, invoice_date, total_cents)
            if result is None:
                continue
            entry, strategy, confidence, candidates, extra = result
            anomalies.extend(a for a in extra if a not in anomalies)

            if entry is not None and self.index.is_duplicated(entry.order_id):
                # One choke point for every rung of the ladder. The ledger
                # holds more than one row for this order, so there is no single
                # entry to pay against. Picking one would be a coin flip with
                # someone else's money; both rows go to a human instead.
                rows = self.index.rows_for_order(entry.order_id)
                for name in (Anomaly.DUPLICATE_ORDER_IN_ERP.value,
                             Anomaly.AMBIGUOUS_CANDIDATES.value):
                    if name not in anomalies:
                        anomalies.append(name)
                return Resolution(
                    entry=None,
                    strategy=strategy,
                    confidence=Confidence.NONE,
                    candidates=tuple(rows),
                    anomalies=tuple(anomalies),
                    notes=tuple(notes) + (
                        f"{len(rows)} ERP rows share {entry.order_id}: "
                        + ", ".join(row.entry_id for row in rows),
                    ),
                )

            if entry is not None:
                anomalies.extend(
                    a for a in self._verify(entry, tax_id, invoice_date, total_cents)
                    if a not in anomalies
                )
                if strategy is not Strategy.ORDER_CODE:
                    if Anomaly.RESOLVED_WITHOUT_ORDER_CODE.value not in anomalies:
                        anomalies.append(Anomaly.RESOLVED_WITHOUT_ORDER_CODE.value)
            return Resolution(
                entry=entry,
                strategy=strategy,
                confidence=confidence,
                candidates=tuple(candidates),
                anomalies=tuple(anomalies),
                notes=tuple(notes),
            )

        return Resolution(
            entry=None,
            strategy=Strategy.NONE,
            confidence=Confidence.NONE,
            candidates=(),
            anomalies=tuple(anomalies),
            notes=tuple(notes),
        )

    # -- rungs of the ladder ----------------------------------------------

    def _by_stated_code(self, signals, tax_id, invoice_date, total_cents):
        codes = find_order_codes(signals.purchase_order or "")
        if not codes:
            codes = find_order_codes(signals.raw_text)
        if not codes:
            return None

        extra: list[str] = []
        if len(codes) > 1:
            extra.append(Anomaly.MULTIPLE_ORDER_CODES.value)
            known = [c for c in codes if self.index.known_order(c)]
            if len(known) != 1:
                candidates = [row for c in codes for row in self.index.rows_for_order(c)]
                return (None, Strategy.ORDER_CODE, Confidence.NONE, candidates,
                        extra + [Anomaly.AMBIGUOUS_CANDIDATES.value])
            codes = known

        code = codes[0]

        if self.index.is_duplicated(code):
            # The ERP holds several rows for this order. Report it as the
            # defect it is; the guard in resolve() would catch it anyway, but
            # saying so here keeps the reason precise.
            rows = self.index.rows_for_order(code)
            return (None, Strategy.ORDER_CODE, Confidence.NONE, rows,
                    extra + [Anomaly.DUPLICATE_ORDER_IN_ERP.value,
                             Anomaly.AMBIGUOUS_CANDIDATES.value])

        entry = self.index.by_order(code)
        if entry is None:
            # The document names an order the ERP has never heard of. That is a
            # finding in its own right, not a reason to go hunting for a
            # different entry that happens to fit.
            extra.append(Anomaly.ORDER_CODE_UNKNOWN_TO_ERP.value)
            return None, Strategy.ORDER_CODE, Confidence.NONE, [], extra
        return entry, Strategy.ORDER_CODE, Confidence.EXACT, [entry], extra

    def _by_repaired_code(self, signals, tax_id, invoice_date, total_cents):
        if not self.repair_order_codes:
            return None
        haystack = " ".join(filter(None, [signals.purchase_order or "", signals.raw_text]))
        proposals = [c for c in repair_order_code(haystack) if self.index.by_order(c)]
        if not proposals:
            return None
        if len(proposals) > 1:
            return (None, Strategy.ORDER_CODE_REPAIRED, Confidence.NONE,
                    [self.index.by_order(c) for c in proposals],
                    [Anomaly.ORDER_CODE_REPAIRED.value, Anomaly.AMBIGUOUS_CANDIDATES.value])
        entry = self.index.by_order(proposals[0])
        # A repair is only credible if something else about the invoice agrees.
        corroborated = (tax_id and entry.tax_id == tax_id) or \
                       (total_cents is not None and entry.amount_cents == total_cents)
        confidence = Confidence.HIGH if corroborated else Confidence.LOW
        return (entry, Strategy.ORDER_CODE_REPAIRED, confidence, [entry],
                [Anomaly.NO_ORDER_CODE.value, Anomaly.ORDER_CODE_REPAIRED.value])

    def _by_nif_and_date(self, signals, tax_id, invoice_date, total_cents):
        """The workhorse. Date anchors, amount only breaks ties."""
        if not tax_id or invoice_date is None:
            return None
        candidates = self.index.by_nif_and_date(tax_id, invoice_date, self.date_window_days)
        if not candidates:
            return None
        extra = [Anomaly.NO_ORDER_CODE.value]
        if len(candidates) == 1:
            return candidates[0], Strategy.NIF_AND_DATE, Confidence.HIGH, candidates, extra

        if total_cents is None:
            return (None, Strategy.NIF_AND_DATE, Confidence.NONE, candidates,
                    extra + [Anomaly.AMBIGUOUS_CANDIDATES.value])

        # Require an exact hit to break the tie. Choosing the "closest" amount
        # would quietly absorb precisely the discrepancies we are looking for.
        exact = [e for e in candidates if e.amount_cents == total_cents]
        if len(exact) == 1:
            return exact[0], Strategy.NIF_AND_DATE, Confidence.HIGH, candidates, extra
        return (None, Strategy.NIF_AND_DATE, Confidence.NONE, candidates,
                extra + [Anomaly.AMBIGUOUS_CANDIDATES.value])

    def _by_nif_and_amount(self, signals, tax_id, invoice_date, total_cents):
        """Used when the date is unreadable or impossible."""
        if not tax_id or total_cents is None:
            return None
        candidates = self.index.by_nif_and_amount(tax_id, total_cents)
        if not candidates:
            return None
        extra = [Anomaly.NO_ORDER_CODE.value]
        if len(candidates) == 1:
            return candidates[0], Strategy.NIF_AND_AMOUNT, Confidence.MEDIUM, candidates, extra
        return (None, Strategy.NIF_AND_AMOUNT, Confidence.NONE, candidates,
                extra + [Anomaly.AMBIGUOUS_CANDIDATES.value])

    def _by_amount_only(self, signals, tax_id, invoice_date, total_cents):
        """Last resort, for invoices whose supplier tax id could not be read."""
        if not self.allow_amount_only or total_cents is None:
            return None
        candidates = self.index.by_amount(total_cents)
        if not candidates:
            return None
        extra = [Anomaly.NO_ORDER_CODE.value]
        if len(candidates) == 1:
            return candidates[0], Strategy.AMOUNT_ONLY, Confidence.LOW, candidates, extra
        return (None, Strategy.AMOUNT_ONLY, Confidence.NONE, candidates,
                extra + [Anomaly.AMBIGUOUS_CANDIDATES.value])

    # -- corroboration -----------------------------------------------------

    def _verify(self, entry: Entry, tax_id: str, invoice_date, total_cents) -> list[str]:
        """Cross-check the match. Runs whatever rung found the entry.

        These checks also guard the happy path: an order code read correctly
        but belonging to a different supplier is exactly how an impersonation
        gets through.
        """
        found: list[str] = []
        if not entry.tax_id:
            found.append(Anomaly.ENTRY_TAX_ID_MISSING.value)
        elif tax_id and entry.tax_id != tax_id:
            found.append(Anomaly.SUPPLIER_TAX_ID_MISMATCH.value)
        if invoice_date and entry.date and invoice_date != entry.date:
            found.append(Anomaly.DATE_MISMATCH.value)
        # The challenge allows a one-cent rounding difference between invoice
        # and order.  Keep this check in cents so the tolerance is exact.
        if total_cents is not None and entry.amount_cents is not None \
                and abs(total_cents - entry.amount_cents) > 1:
            found.append(Anomaly.AMOUNT_MISMATCH.value)
        if entry.status.upper() == "PAGADA":
            found.append(Anomaly.ENTRY_ALREADY_PAID.value)
        if entry.warnings:
            found.append(Anomaly.ENTRY_HAS_WARNINGS.value)
        return found

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _tax_id_from_text(text: str) -> str:
        for match in TAX_ID.finditer(text or ""):
            candidate = normalise_tax_id(match.group(1))
            if candidate and candidate != CLIENT_TAX_ID:
                return candidate
        return ""
