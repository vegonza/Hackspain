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

from .constants import (
    CLIENT_TAX_ID,
    GLYPH_TO_DIGIT,
    ORDER_CODE,
    ORDER_CODE_LOOSE,
    SPANISH_MONTHS,
    TAX_ID,
)
from .enums import (
    BLOCKING_ANOMALIES,
    Anomaly,
    Confidence,
    Strategy,
)
from .index import ErpIndex
from .models import (
    Entry,
    InvoiceSignals,
    Resolution,
)
from .normalisation import (
    find_order_codes,
    normalise_amount,
    normalise_date,
    normalise_name,
    normalise_tax_id,
    repair_order_code,
)
from .resolver import OrderResolver

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
    "normalise_name",
    "normalise_tax_id",
    "repair_order_code",
    "find_order_codes",
]
