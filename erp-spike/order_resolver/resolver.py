#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import date

from .constants import CLIENT_TAX_ID, TAX_ID
from .enums import Anomaly, Confidence, Strategy
from .index import ErpIndex
from .models import Entry, InvoiceSignals, Resolution
from .normalisation import (
    find_order_codes,
    normalise_amount,
    normalise_date,
    normalise_tax_id,
    repair_order_code,
)


class OrderResolver:
    """Map an invoice onto an ERP entry, or explain why it cannot be done."""

    def __init__(
        self,
        index: ErpIndex,
        *,
        date_window_days: int = 0,
        allow_amount_only: bool = True,
        repair_order_codes: bool = True,
    ) -> None:
        self.index = index
        self.date_window_days = date_window_days
        self.allow_amount_only = allow_amount_only
        self.repair_order_codes = repair_order_codes

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

        # Whatever the document claims, recorded before any of it is judged.
        # The ERP may disown the code, the cascade may fall through to another
        # rung, the answer may be no answer at all: none of that is a reason to
        # forget what was written on the paper. A caller that has to look the
        # order up somewhere else needs it exactly when we could not.
        stated = self._stated_codes(signals)

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
                for name in (
                    Anomaly.DUPLICATE_ORDER_IN_ERP.value,
                    Anomaly.AMBIGUOUS_CANDIDATES.value,
                ):
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
                    stated_order_ids=stated,
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
                stated_order_ids=stated,
            )

        return Resolution(
            entry=None,
            strategy=Strategy.NONE,
            confidence=Confidence.NONE,
            candidates=(),
            anomalies=tuple(anomalies),
            notes=tuple(notes),
            stated_order_ids=stated,
        )

    @staticmethod
    def _stated_codes(signals: InvoiceSignals) -> tuple[str, ...]:
        """Order codes the document states: the field first, then the text.

        The dedicated field wins when it holds one, because the extraction
        layer has already decided that is the order. Only when it is empty is
        the body searched, and then by pattern rather than by label: the corpus
        puts six different labels in front of the code, so matching on the
        label alone would miss most of them.
        """
        codes = find_order_codes(signals.purchase_order or "")
        return tuple(codes or find_order_codes(signals.raw_text))

    def _by_stated_code(
        self,
        signals: InvoiceSignals,
        tax_id: str,
        invoice_date: date | None,
        total_cents: int | None,
    ) -> tuple[Entry | None, Strategy, Confidence, list[Entry], list[str]] | None:
        # Same source as Resolution.stated_order_ids, deliberately: what the
        # ladder searches on and what the result reports must never drift.
        codes = list(self._stated_codes(signals))
        if not codes:
            return None

        extra: list[str] = []
        if len(codes) > 1:
            extra.append(Anomaly.MULTIPLE_ORDER_CODES.value)
            known = [c for c in codes if self.index.known_order(c)]
            if len(known) != 1:
                candidates = [row for c in codes for row in self.index.rows_for_order(c)]
                return (
                    None,
                    Strategy.ORDER_CODE,
                    Confidence.NONE,
                    candidates,
                    extra + [Anomaly.AMBIGUOUS_CANDIDATES.value],
                )
            codes = known

        code = codes[0]

        if self.index.is_duplicated(code):
            # The ERP holds several rows for this order. Report it as the
            # defect it is; the guard in resolve() would catch it anyway, but
            # saying so here keeps the reason precise.
            rows = self.index.rows_for_order(code)
            return (
                None,
                Strategy.ORDER_CODE,
                Confidence.NONE,
                rows,
                extra + [
                    Anomaly.DUPLICATE_ORDER_IN_ERP.value,
                    Anomaly.AMBIGUOUS_CANDIDATES.value,
                ],
            )

        entry = self.index.by_order(code)
        if entry is None:
            # The document names an order the ERP has never heard of. That is a
            # finding in its own right, not a reason to go hunting for a
            # different entry that happens to fit.
            extra.append(Anomaly.ORDER_CODE_UNKNOWN_TO_ERP.value)
            return None, Strategy.ORDER_CODE, Confidence.NONE, [], extra
        return entry, Strategy.ORDER_CODE, Confidence.EXACT, [entry], extra

    def _by_repaired_code(
        self,
        signals: InvoiceSignals,
        tax_id: str,
        invoice_date: date | None,
        total_cents: int | None,
    ) -> tuple[Entry | None, Strategy, Confidence, list[Entry], list[str]] | None:
        if not self.repair_order_codes:
            return None
        haystack = " ".join(filter(None, [signals.purchase_order or "", signals.raw_text]))
        proposals = [c for c in repair_order_code(haystack) if self.index.by_order(c)]
        if not proposals:
            return None
        if len(proposals) > 1:
            matching_entries = [e for c in proposals if (e := self.index.by_order(c)) is not None]
            return (
                None,
                Strategy.ORDER_CODE_REPAIRED,
                Confidence.NONE,
                matching_entries,
                [Anomaly.ORDER_CODE_REPAIRED.value, Anomaly.AMBIGUOUS_CANDIDATES.value],
            )
        entry = self.index.by_order(proposals[0])
        if entry is None:
            return None
        # A repair is only credible if something else about the invoice agrees.
        corroborated = (tax_id and entry.tax_id == tax_id) or (
            total_cents is not None and entry.amount_cents == total_cents
        )
        confidence = Confidence.HIGH if corroborated else Confidence.LOW
        return (
            entry,
            Strategy.ORDER_CODE_REPAIRED,
            confidence,
            [entry],
            [Anomaly.NO_ORDER_CODE.value, Anomaly.ORDER_CODE_REPAIRED.value],
        )

    def _by_nif_and_date(
        self,
        signals: InvoiceSignals,
        tax_id: str,
        invoice_date: date | None,
        total_cents: int | None,
    ) -> tuple[Entry | None, Strategy, Confidence, list[Entry], list[str]] | None:
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
            return (
                None,
                Strategy.NIF_AND_DATE,
                Confidence.NONE,
                candidates,
                extra + [Anomaly.AMBIGUOUS_CANDIDATES.value],
            )

        # Require an exact hit to break the tie. Choosing the "closest" amount
        # would quietly absorb precisely the discrepancies we are looking for.
        exact = [e for e in candidates if e.amount_cents == total_cents]
        if len(exact) == 1:
            return exact[0], Strategy.NIF_AND_DATE, Confidence.HIGH, candidates, extra
        return (
            None,
            Strategy.NIF_AND_DATE,
            Confidence.NONE,
            candidates,
            extra + [Anomaly.AMBIGUOUS_CANDIDATES.value],
        )

    def _by_nif_and_amount(
        self,
        signals: InvoiceSignals,
        tax_id: str,
        invoice_date: date | None,
        total_cents: int | None,
    ) -> tuple[Entry | None, Strategy, Confidence, list[Entry], list[str]] | None:
        """Used when the date is unreadable or impossible."""
        if not tax_id or total_cents is None:
            return None
        candidates = self.index.by_nif_and_amount(tax_id, total_cents)
        if not candidates:
            return None
        extra = [Anomaly.NO_ORDER_CODE.value]
        if len(candidates) == 1:
            return candidates[0], Strategy.NIF_AND_AMOUNT, Confidence.MEDIUM, candidates, extra
        return (
            None,
            Strategy.NIF_AND_AMOUNT,
            Confidence.NONE,
            candidates,
            extra + [Anomaly.AMBIGUOUS_CANDIDATES.value],
        )

    def _by_amount_only(
        self,
        signals: InvoiceSignals,
        tax_id: str,
        invoice_date: date | None,
        total_cents: int | None,
    ) -> tuple[Entry | None, Strategy, Confidence, list[Entry], list[str]] | None:
        """Last resort, for invoices whose supplier tax id could not be read."""
        if not self.allow_amount_only or total_cents is None:
            return None
        candidates = self.index.by_amount(total_cents)
        if not candidates:
            return None
        extra = [Anomaly.NO_ORDER_CODE.value]
        if len(candidates) == 1:
            return candidates[0], Strategy.AMOUNT_ONLY, Confidence.LOW, candidates, extra
        return (
            None,
            Strategy.AMOUNT_ONLY,
            Confidence.NONE,
            candidates,
            extra + [Anomaly.AMBIGUOUS_CANDIDATES.value],
        )

    def _verify(
        self,
        entry: Entry,
        tax_id: str,
        invoice_date: date | None,
        total_cents: int | None,
    ) -> list[str]:
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
        if (
            total_cents is not None
            and entry.amount_cents is not None
            and abs(total_cents - entry.amount_cents) > 1
        ):
            found.append(Anomaly.AMOUNT_MISMATCH.value)
        if entry.status.upper() == "PAGADA":
            found.append(Anomaly.ENTRY_ALREADY_PAID.value)
        if entry.warnings:
            found.append(Anomaly.ENTRY_HAS_WARNINGS.value)
        return found

    @staticmethod
    def _tax_id_from_text(text: str) -> str:
        for match in TAX_ID.finditer(text or ""):
            candidate = normalise_tax_id(match.group(1))
            if candidate and candidate != CLIENT_TAX_ID:
                return candidate
        return ""
