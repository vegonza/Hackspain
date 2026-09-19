#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Mapping

from .enums import BLOCKING_ANOMALIES, Confidence, Strategy
from .normalisation import normalise_amount, normalise_date, normalise_tax_id


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
    def from_dict(cls, data: dict[str, object] | Mapping[str, object]) -> Entry:
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
    def from_features(cls, features: object, raw_text: str = "", source_name: str = "") -> InvoiceSignals:
        """Adapt a backend ``InvoiceFeatures`` object or plain mapping."""
        get = features.get if isinstance(features, Mapping) else (
            lambda key, default=None: getattr(features, key, default)
        )
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
    #: Every order code the document itself states, whether or not the ERP has
    #: ever heard of it. Kept separate from :attr:`order_id` on purpose; see
    #: that property for why the two must not be merged.
    stated_order_ids: tuple[str, ...] = ()

    @property
    def order_id(self) -> str | None:
        """The order the **ledger** confirmed, or None.

        This is deliberately not "the order number we saw somewhere". An
        invoice can name an order the ERP has never heard of: three documents
        in the corpus do exactly that. For those the ledger has confirmed
        nothing, so this returns None and the claimed code is available from
        :attr:`stated_order_id` instead.

        Keeping the two apart is the whole point. If this fell back to the
        claimed code, ``if res.order_id: pay_against(res.order_id)`` would pay
        against an order no accounting system can vouch for, and the caller
        would have no way to tell the two situations apart.
        """
        return self.entry.order_id if self.entry else None

    @property
    def stated_order_id(self) -> str | None:
        """The single order code the **document** claims, or None.

        None both when the document names no order and when it names more than
        one, because then there is no single answer to give. The full list is
        always in :attr:`stated_order_ids`, and the ``multiple_order_codes``
        anomaly says so explicitly.
        """
        return self.stated_order_ids[0] if len(self.stated_order_ids) == 1 else None

    @property
    def order_id_source(self) -> str:
        """Where the order number came from, for a caller that must choose.

        ``"erp"``       the ledger confirmed it.
        ``"document"``  only the paper says so; nothing has corroborated it.
        ``"none"``      no order number at all, from either side.
        """
        if self.entry is not None:
            return "erp"
        if self.stated_order_ids:
            return "document"
        return "none"

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

    def to_dict(self) -> dict[str, object]:
        return {
            "order_id": self.order_id,
            "stated_order_id": self.stated_order_id,
            "stated_order_ids": list(self.stated_order_ids),
            "order_id_source": self.order_id_source,
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
