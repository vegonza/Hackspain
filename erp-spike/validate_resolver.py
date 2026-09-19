#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Measure order_resolver against the real invoice corpus.

Two passes over the same 500 documents:

  1. as they are, with the purchase order code visible;
  2. blind, with the code stripped out, which is how we expect at least some
     of the incoming invoices to arrive.

The number that matters is not the hit rate, it is the false positive count.
A resolver that escalates is merely slow; a resolver that confidently returns
the wrong order causes a wrong payment.

Usage:
    python3 validate_resolver.py
    ERP_SNAPSHOT_PATH=/some/where.jsonl python3 validate_resolver.py
"""
from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path

from order_resolver import ErpIndex, OrderResolver, Strategy

try:
    # Stand-in for the OCR layer. Not distributed with the module: the real
    # extraction is the backend's Mistral pipeline, which fills InvoiceFeatures.
    from fake_ocr import signals_from_raw_text
except ImportError:
    signals_from_raw_text = None

HERE = Path(__file__).resolve().parent
DATA = Path(os.environ.get("ERP_DATA_DIR", HERE / "data"))
ERP_SNAPSHOT = Path(os.environ.get("ERP_SNAPSHOT_PATH", DATA / "erp_entries.jsonl"))
INVOICES = Path(os.environ.get("INVOICES_EXTRACTED_PATH", DATA / "invoices_extracted.jsonl"))

MISSING_INPUTS = """\
This harness replays the real invoice corpus, which is not in the repository.
It needs three things:

  1. {snapshot}
     produced by:  python3 erp_client.py --output data/erp_entries.jsonl

  2. {invoices}
     produced by:  python3 tools/extract_invoices.py /path/to/facturas

  3. fake_ocr.py, a stand-in for the OCR layer
     not distributed; once InvoiceFeatures carries real values, feed those
     to OrderResolver.resolve() through InvoiceSignals.from_features()
     and delete the stand-in entirely.

Missing: {missing}
"""


def preflight() -> None:
    """Fail once, naming everything that is missing, instead of one at a time."""
    missing = []
    if not ERP_SNAPSHOT.exists():
        missing.append(str(ERP_SNAPSHOT))
    if not INVOICES.exists():
        missing.append(str(INVOICES))
    if signals_from_raw_text is None:
        missing.append("fake_ocr.py")
    if missing:
        raise SystemExit(MISSING_INPUTS.format(
            snapshot=ERP_SNAPSHOT, invoices=INVOICES, missing=", ".join(missing)))


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def scoreable(records, index):
    """Only invoices whose true order is known and present in the ERP."""
    for record in records:
        codes = record.get("orders_canonical") or []
        if not codes:
            continue
        if index.by_order(codes[0]) is None:
            continue
        yield record, codes[0]


def run(records, index, blind: bool) -> dict:
    resolver = OrderResolver(index)
    heading = "SIN CODIGO DE PEDIDO (simulado)" if blind else "CON CODIGO DE PEDIDO"
    print()
    print("=" * 96)
    print(f"  {heading}")
    print("=" * 96)

    strategies: Counter = Counter()
    confidences: Counter = Counter()
    correct = wrong = unresolved = review = 0
    wrong_cases, unresolved_cases, shortlist_sizes = [], [], []

    for record, truth in scoreable(records, index):
        signals = signals_from_raw_text(
            record["text"],
            purchase_order=truth,
            blind=blind,
            source_name=record["file"],
        )
        result = resolver.resolve(signals)
        strategies[result.strategy.value] += 1
        confidences[result.confidence.value] += 1
        review += bool(result.needs_review)

        if not result.resolved:
            unresolved += 1
            shortlist_sizes.append(len(result.candidates))
            unresolved_cases.append((record["file"], truth, result))
        elif result.order_id == truth:
            correct += 1
        else:
            wrong += 1
            wrong_cases.append((record["file"], truth, result))

    total = correct + wrong + unresolved
    print(f"  facturas evaluadas          : {total}")
    print(f"  ACIERTA                     : {correct} ({100 * correct / total:.1f}%)")
    print(f"  SE EQUIVOCA (falso positivo): {wrong}")
    print(f"  no resuelve -> escalar      : {unresolved} ({100 * unresolved / total:.1f}%)")
    print(f"  marcadas para revision      : {review}")
    print(f"  estrategias                 : {dict(strategies)}")
    print(f"  confianza                   : {dict(confidences)}")
    if shortlist_sizes:
        avg = sum(shortlist_sizes) / len(shortlist_sizes)
        print(f"  candidatos al escalar       : media {avg:.1f}, maximo {max(shortlist_sizes)}")

    if wrong_cases:
        print()
        print("  --- FALSOS POSITIVOS ---")
        for name, truth, result in wrong_cases:
            print(f"    {name:32} real={truth} dijo={result.order_id} "
                  f"via={result.strategy.value}")

    if unresolved_cases:
        in_shortlist = sum(
            1 for _, truth, result in unresolved_cases
            if truth in {c.order_id for c in result.candidates}
        )
        print()
        print(f"  --- NO RESUELTAS ({len(unresolved_cases)}) ---")
        print(f"  el pedido correcto esta entre los candidatos: "
              f"{in_shortlist}/{len(unresolved_cases)}")
        for name, truth, result in unresolved_cases[:40]:
            shortlist = ",".join(c.order_id for c in result.candidates[:4]) or "-"
            print(f"    {name:30} real={truth} [{shortlist}] "
                  f"motivos={','.join(result.anomalies)}")

    return {"correct": correct, "wrong": wrong, "unresolved": unresolved}


def main() -> None:
    preflight()
    index = ErpIndex(load_jsonl(ERP_SNAPSHOT))
    records = load_jsonl(INVOICES)
    print(f"asientos indexados : {len(index)}   ({ERP_SNAPSHOT})")
    print(f"facturas leidas    : {len(records)} ({INVOICES})")
    print(f"order_id duplicados: {index.duplicate_order_ids or 'ninguno'}")

    with_code = run(records, index, blind=False)
    without_code = run(records, index, blind=True)

    print()
    print("=" * 96)
    print("  VEREDICTO")
    print("=" * 96)
    failures = with_code["wrong"] + without_code["wrong"]
    if failures:
        raise SystemExit(f"  FALLO: {failures} falsos positivos")
    print("  0 falsos positivos en ambos modos.")
    print("  Cuando no puede decidir, escala con la lista corta de candidatos.")


if __name__ == "__main__":
    main()
