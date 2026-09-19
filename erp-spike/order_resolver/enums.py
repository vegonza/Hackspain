#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from enum import Enum


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
BLOCKING_ANOMALIES: frozenset[str] = frozenset({
    Anomaly.ENTRY_ALREADY_PAID.value,
    Anomaly.DUPLICATE_ORDER_IN_ERP.value,
    Anomaly.SUPPLIER_TAX_ID_MISMATCH.value,
    Anomaly.ORDER_CODE_UNKNOWN_TO_ERP.value,
    Anomaly.INVOICE_DATE_IMPOSSIBLE.value,
})
