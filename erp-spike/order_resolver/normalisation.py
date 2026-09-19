#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import unicodedata
from datetime import date

from .constants import (
    AMOUNT_EN_GROUPED,
    AMOUNT_EN_PLAIN,
    AMOUNT_ES_GROUPED,
    AMOUNT_ES_PLAIN,
    AMOUNT_INTEGER,
    DATE_ISO,
    DATE_NUMERIC,
    DATE_WORDS,
    GLYPH_TO_DIGIT,
    ORDER_CODE,
    ORDER_CODE_LOOSE,
    SPANISH_MONTHS,
)
from .enums import Anomaly


def normalise_amount(raw: object) -> int | None:
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

    if AMOUNT_ES_GROUPED.match(text):
        digits = text.replace(".", "").replace(",", ".")
    elif AMOUNT_ES_PLAIN.match(text):
        digits = text.replace(",", ".")
    elif AMOUNT_EN_GROUPED.match(text):
        digits = text.replace(",", "")
    elif AMOUNT_EN_PLAIN.match(text):
        digits = text
    elif AMOUNT_INTEGER.match(text):
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


def normalise_date(raw: object) -> tuple[date | None, str | None]:
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

    match = DATE_ISO.search(text)
    if match:
        year, month, day = (int(x) for x in match.groups())
        return _build_date(year, month, day)

    match = DATE_NUMERIC.search(text)
    if match:
        day, month, year = (int(x) for x in match.groups())
        return _build_date(year, month, day)

    match = DATE_WORDS.search(text)
    if match:
        day_str, word, year_str = match.group(1), match.group(2), match.group(3)
        key = _strip_accents(word).lower()
        month = SPANISH_MONTHS.get(key)
        if month:
            return _build_date(int(year_str), month, int(day_str))

    return None, Anomaly.INVOICE_DATE_UNPARSEABLE.value


def _build_date(year: int, month: int, day: int) -> tuple[date | None, str | None]:
    try:
        return date(year, month, day), None
    except ValueError:
        return None, Anomaly.INVOICE_DATE_IMPOSSIBLE.value


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text)
                   if unicodedata.category(c) != "Mn")


def normalise_tax_id(raw: object) -> str:
    if not raw:
        return ""
    return re.sub(r"[^A-Z0-9]", "", str(raw).upper())


def normalise_name(raw: object) -> str:
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
