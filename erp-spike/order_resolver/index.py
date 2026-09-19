#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from .models import Entry


class ErpIndex:
    """In-memory indexes over the ERP snapshot.

    Built once, queried many times. Every lookup the resolver needs is O(1) or
    O(size of a small bucket), so the cascade stays cheap even when it has to
    try every rung.
    """

    def __init__(self, entries: Iterable[dict[str, object] | Mapping[str, object] | Entry]) -> None:
        grouped: dict[str, list[Entry]] = {}
        self._all: list[Entry] = []

        for item in entries:
            entry = item if isinstance(item, Entry) else Entry.from_dict(item)
            if not entry.order_id:
                continue
            grouped.setdefault(entry.order_id, []).append(entry)
            self._all.append(entry)

        self._grouped: dict[str, list[Entry]] = grouped
        self.duplicate_order_ids: list[str] = sorted(o for o, rows in grouped.items() if len(rows) > 1)
        self._duplicated: frozenset[str] = frozenset(self.duplicate_order_ids)

        # Only orders backed by exactly one row are directly addressable. A
        # duplicated order is not a row we may choose between; it is a defect
        # in the ledger, and choosing would hide it.
        self._by_order: dict[str, Entry] = {o: rows[0] for o, rows in grouped.items() if len(rows) == 1}

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
    def from_jsonl(cls, path: str | Path) -> ErpIndex:
        """Build the index straight from the file erp_client writes.

        This is the whole integration surface: there is no service to call and
        nothing to keep running. The dumper produces a file, the consumer reads
        it. If the file is missing the caller gets FileNotFoundError at startup,
        which is the right moment to find out.
        """
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
