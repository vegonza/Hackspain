#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for order_resolver.

The corpus-backed tests at the bottom are the ones that matter most: they pin
the behaviour that was measured against the real 500 invoices, so a future
change that quietly starts guessing will fail here.
"""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

import pytest

try:
    # A stand-in for the OCR layer, used only by the corpus regression tests.
    # It is not distributed: the real extraction is the backend's OCR pipeline.
    from fake_ocr import signals_from_raw_text
except ImportError:
    signals_from_raw_text = None
from order_resolver import (
    Anomaly,
    Confidence,
    ErpIndex,
    Entry,
    InvoiceSignals,
    OrderResolver,
    Strategy,
    find_order_codes,
    normalise_amount,
    normalise_date,
    normalise_name,
    normalise_tax_id,
    repair_order_code,
)

HERE = Path(__file__).resolve().parent
DATA = Path(os.environ.get("ERP_DATA_DIR", HERE / "data"))
ERP_SNAPSHOT = Path(os.environ.get("ERP_SNAPSHOT_PATH", DATA / "erp_entries.jsonl"))
INVOICES = Path(os.environ.get("INVOICES_EXTRACTED_PATH", DATA / "invoices_extracted.jsonl"))


# --------------------------------------------------------------------------
# Amounts
# --------------------------------------------------------------------------

class TestNormaliseAmount:
    @pytest.mark.parametrize("raw,cents", [
        ("1.250,00", 125000),
        ("2.489,99", 248999),
        ("943,80", 94380),
        ("12.874,40", 1287440),
        ("1.250,00 €", 125000),
        ("Importe base: 1.250,00 €", None),  # a whole sentence is not an amount
    ])
    def test_spanish_convention(self, raw, cents):
        assert normalise_amount(raw) == cents

    @pytest.mark.parametrize("raw,cents", [
        ("3400.00", 340000),
        ("EUR 1409.40", 140940),
        ("1705.37", 170537),
        ("930.20", 93020),
    ])
    def test_english_convention(self, raw, cents):
        assert normalise_amount(raw) == cents

    def test_the_trap_that_would_multiply_by_a_hundred(self):
        # Stripping dots blindly turns 3400.00 into 340000,00. Both must survive.
        assert normalise_amount("3400.00") == 340000
        assert normalise_amount("3.400,00") == 340000

    def test_ambiguous_shape_is_refused_rather_than_guessed(self):
        # "1,234" is 1.234 in English and 1,23 rounded in Spanish. Neither.
        assert normalise_amount("1,234") is None

    @pytest.mark.parametrize("raw", ["", "   ", None, "n/d", "€", "--"])
    def test_junk_returns_none(self, raw):
        assert normalise_amount(raw) is None

    def test_numeric_inputs_pass_through(self):
        assert normalise_amount(1250) == 125000
        assert normalise_amount(1250.5) == 125050

    def test_integer_cents_avoid_float_drift(self):
        assert normalise_amount("0,10") + normalise_amount("0,20") == normalise_amount("0,30")


# --------------------------------------------------------------------------
# Dates
# --------------------------------------------------------------------------

class TestNormaliseDate:
    @pytest.mark.parametrize("raw,expected", [
        ("08/01/2026", date(2026, 1, 8)),
        ("26/01/2026", date(2026, 1, 26)),
        ("2026-04-07", date(2026, 4, 7)),
        ("7 de abril de 2026", date(2026, 4, 7)),
        ("17 de septiembre de 2026", date(2026, 9, 17)),
        ("Fecha factura: 18/06/2026", date(2026, 6, 18)),
    ])
    def test_every_layout_in_the_corpus(self, raw, expected):
        parsed, anomaly = normalise_date(raw)
        assert parsed == expected
        assert anomaly is None

    @pytest.mark.parametrize("raw", ["31/02/2026", "30/02/2026", "32/01/2026", "15/13/2026"])
    def test_impossible_dates_are_flagged_distinctly(self, raw):
        parsed, anomaly = normalise_date(raw)
        assert parsed is None
        assert anomaly == Anomaly.INVOICE_DATE_IMPOSSIBLE.value

    @pytest.mark.parametrize("raw", ["", None, "pendiente", "a determinar"])
    def test_unreadable_is_not_the_same_as_impossible(self, raw):
        parsed, anomaly = normalise_date(raw)
        assert parsed is None
        assert anomaly == Anomaly.INVOICE_DATE_UNPARSEABLE.value

    def test_accented_month_is_accepted(self):
        assert normalise_date("3 de diciembre de 2026")[0] == date(2026, 12, 3)

    def test_day_month_order_is_spanish_not_american(self):
        assert normalise_date("08/01/2026")[0] == date(2026, 1, 8)


# --------------------------------------------------------------------------
# Order codes
# --------------------------------------------------------------------------

class TestOrderCodes:
    def test_finds_the_code_regardless_of_label(self):
        for label in ("Ref. Pedido", "Su pedido", "PO", "Pedido",
                      "PEDIDO CLIENTE", "Pedido asociado"):
            assert find_order_codes(f"{label}: PO-2026-0096") == ["PO-2026-0096"]

    def test_repeated_code_on_a_multipage_invoice_collapses(self):
        text = "Ref. Pedido: PO-2026-0469\nSuma y sigue\nRef. Pedido: PO-2026-0469"
        assert find_order_codes(text) == ["PO-2026-0469"]

    def test_two_different_codes_are_both_reported(self):
        text = "PO-2026-0469 y tambien PO-2026-0470"
        assert find_order_codes(text) == ["PO-2026-0469", "PO-2026-0470"]

    @pytest.mark.parametrize("damaged,expected", [
        ("PO-2026-OO42", "PO-2026-0042"),
        ("P0-2026-0042", "PO-2026-0042"),
        ("PO 2026 0042", "PO-2026-0042"),
        ("PO_2026_0042", "PO-2026-0042"),
        ("PO-2026-42", "PO-2026-0042"),
        ("PO-2026-S042", None),   # 5 digits: not a plausible repair
    ])
    def test_glyph_repair(self, damaged, expected):
        proposals = repair_order_code(damaged)
        if expected is None:
            assert expected not in proposals
        else:
            assert expected in proposals

    def test_repair_never_invents_from_nothing(self):
        assert repair_order_code("factura sin ninguna referencia") == []


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

def make_entry(order, nif="B11111111", day="2026-03-01", amount="100.00",
               status="PENDIENTE", entry_id=None, warnings=()):
    return {
        "entry_id": entry_id or order.replace("PO-2026-", "AS-00"),
        "order_id": order,
        "supplier_id": "P001",
        "tax_id": nif,
        "status": status,
        "date": day,
        "amount": amount,
        "raw_date": "",
        "raw_amount": "",
        "warnings": list(warnings),
    }


@pytest.fixture
def small_index():
    return ErpIndex([
        make_entry("PO-2026-0001", nif="B11111111", day="2026-03-01", amount="100.00"),
        make_entry("PO-2026-0002", nif="B11111111", day="2026-03-02", amount="200.00"),
        # same supplier, same day: only the amount tells them apart
        make_entry("PO-2026-0003", nif="B11111111", day="2026-03-03", amount="300.00"),
        make_entry("PO-2026-0004", nif="B11111111", day="2026-03-03", amount="400.00"),
        make_entry("PO-2026-0005", nif="B22222222", day="2026-03-05", amount="500.00",
                   status="PAGADA"),
        make_entry("PO-2026-0006", nif="", day="2026-03-06", amount="600.00",
                   warnings=("empty_field:tax_id",)),
    ])


@pytest.fixture
def resolver(small_index):
    return OrderResolver(small_index)


# --------------------------------------------------------------------------
# The cascade
# --------------------------------------------------------------------------

class TestStatedCode:
    def test_happy_path(self, resolver):
        res = resolver.resolve(InvoiceSignals(
            purchase_order="PO-2026-0001", supplier_nif="B11111111",
            invoice_date="01/03/2026", total="100,00"))
        assert res.order_id == "PO-2026-0001"
        assert res.strategy is Strategy.ORDER_CODE
        assert res.confidence is Confidence.EXACT
        assert res.needs_review is False
        assert res.anomalies == ()

    def test_code_recovered_from_raw_text_when_field_is_empty(self, resolver):
        res = resolver.resolve(InvoiceSignals(
            purchase_order=None, supplier_nif="B11111111",
            invoice_date="01/03/2026", total="100,00",
            raw_text="Su pedido: PO-2026-0001"))
        assert res.order_id == "PO-2026-0001"
        assert res.strategy is Strategy.ORDER_CODE

    def test_order_the_erp_does_not_know_falls_through_but_is_flagged(self, resolver):
        res = resolver.resolve(InvoiceSignals(
            purchase_order="PO-2026-9999", supplier_nif="B11111111",
            invoice_date="01/03/2026", total="100,00"))
        assert Anomaly.ORDER_CODE_UNKNOWN_TO_ERP.value in res.anomalies
        # It must NOT quietly rematch onto PO-2026-0001 via the amount.
        assert res.order_id is None

    def test_two_different_codes_refuses_to_pick(self, resolver):
        res = resolver.resolve(InvoiceSignals(
            purchase_order=None, supplier_nif="B11111111",
            raw_text="PO-2026-0001 ... PO-2026-0002"))
        assert Anomaly.MULTIPLE_ORDER_CODES.value in res.anomalies
        assert res.order_id is None


class TestNifAndDate:
    def test_unique_match_without_any_code(self, resolver):
        res = resolver.resolve(InvoiceSignals(
            supplier_nif="B11111111", invoice_date="01/03/2026", total="100,00"))
        assert res.order_id == "PO-2026-0001"
        assert res.strategy is Strategy.NIF_AND_DATE
        assert res.confidence is Confidence.HIGH
        assert Anomaly.RESOLVED_WITHOUT_ORDER_CODE.value in res.anomalies
        assert res.needs_review is True

    def test_tie_is_broken_by_an_exact_amount(self, resolver):
        res = resolver.resolve(InvoiceSignals(
            supplier_nif="B11111111", invoice_date="03/03/2026", total="400,00"))
        assert res.order_id == "PO-2026-0004"

    def test_tie_with_a_non_matching_amount_escalates(self, resolver):
        # 350 is nearer to 300 than to 400, but "nearest" is not evidence.
        res = resolver.resolve(InvoiceSignals(
            supplier_nif="B11111111", invoice_date="03/03/2026", total="350,00"))
        assert res.order_id is None
        assert Anomaly.AMBIGUOUS_CANDIDATES.value in res.anomalies
        assert {c.order_id for c in res.candidates} == {"PO-2026-0003", "PO-2026-0004"}

    def test_candidates_are_returned_so_a_human_has_a_shortlist(self, resolver):
        res = resolver.resolve(InvoiceSignals(
            supplier_nif="B11111111", invoice_date="03/03/2026"))
        assert len(res.candidates) == 2


class TestFallbacksBelowTheDate:
    def test_impossible_date_falls_through_to_nif_and_amount(self, resolver):
        res = resolver.resolve(InvoiceSignals(
            supplier_nif="B11111111", invoice_date="31/02/2026", total="200,00"))
        assert res.order_id == "PO-2026-0002"
        assert res.strategy is Strategy.NIF_AND_AMOUNT
        assert res.confidence is Confidence.MEDIUM
        assert Anomaly.INVOICE_DATE_IMPOSSIBLE.value in res.anomalies

    def test_missing_supplier_falls_through_to_amount_only(self, resolver):
        res = resolver.resolve(InvoiceSignals(invoice_date="02/03/2026", total="200,00"))
        assert res.order_id == "PO-2026-0002"
        assert res.strategy is Strategy.AMOUNT_ONLY
        assert res.confidence is Confidence.LOW
        assert Anomaly.SUPPLIER_TAX_ID_MISSING.value in res.anomalies

    def test_amount_only_can_be_switched_off(self, small_index):
        strict = OrderResolver(small_index, allow_amount_only=False)
        res = strict.resolve(InvoiceSignals(invoice_date="02/03/2026", total="200,00"))
        assert res.order_id is None

    def test_nothing_readable_gives_up_cleanly(self, resolver):
        res = resolver.resolve(InvoiceSignals())
        assert res.order_id is None
        assert res.strategy is Strategy.NONE
        assert res.confidence is Confidence.NONE


class TestCorroboration:
    def test_right_code_wrong_supplier_is_flagged(self, resolver):
        res = resolver.resolve(InvoiceSignals(
            purchase_order="PO-2026-0001", supplier_nif="B99999999",
            invoice_date="01/03/2026", total="100,00"))
        assert res.order_id == "PO-2026-0001"
        assert Anomaly.SUPPLIER_TAX_ID_MISMATCH.value in res.anomalies

    def test_amount_mismatch_survives_resolution(self, resolver):
        # The whole point: finding the entry must not hide the discrepancy.
        res = resolver.resolve(InvoiceSignals(
            purchase_order="PO-2026-0001", supplier_nif="B11111111",
            invoice_date="01/03/2026", total="150,00"))
        assert res.order_id == "PO-2026-0001"
        assert Anomaly.AMOUNT_MISMATCH.value in res.anomalies

    def test_date_mismatch_is_reported(self, resolver):
        res = resolver.resolve(InvoiceSignals(
            purchase_order="PO-2026-0001", supplier_nif="B11111111",
            invoice_date="09/03/2026", total="100,00"))
        assert Anomaly.DATE_MISMATCH.value in res.anomalies

    def test_already_paid_entry_is_reported(self, resolver):
        res = resolver.resolve(InvoiceSignals(
            purchase_order="PO-2026-0005", supplier_nif="B22222222",
            invoice_date="05/03/2026", total="500,00"))
        assert Anomaly.ENTRY_ALREADY_PAID.value in res.anomalies

    def test_entry_without_tax_id_is_reported(self, resolver):
        res = resolver.resolve(InvoiceSignals(
            purchase_order="PO-2026-0006", supplier_nif="B33333333",
            invoice_date="06/03/2026", total="600,00"))
        assert Anomaly.ENTRY_TAX_ID_MISSING.value in res.anomalies
        assert Anomaly.ENTRY_HAS_WARNINGS.value in res.anomalies
        # A missing tax id must not be reported as a mismatch.
        assert Anomaly.SUPPLIER_TAX_ID_MISMATCH.value not in res.anomalies

    def test_client_tax_id_is_never_taken_for_the_supplier(self, resolver):
        res = resolver.resolve(InvoiceSignals(
            purchase_order="PO-2026-0001", supplier_nif="A58231074",
            invoice_date="01/03/2026", total="100,00"))
        assert Anomaly.SUPPLIER_TAX_ID_MISMATCH.value not in res.anomalies


class TestNormalisationHelpers:
    def test_supplier_names_compare_across_case_and_suffix(self):
        assert normalise_name("Transportes Guadaira S.A.") == \
               normalise_name("TRANSPORTES GUADAIRA S.A.")

    def test_tax_id_ignores_spacing_and_case(self):
        assert normalise_tax_id(" b-96233419 ") == "B96233419"


class TestResolutionContract:
    def test_to_dict_is_serialisable(self, resolver):
        res = resolver.resolve(InvoiceSignals(
            purchase_order="PO-2026-0001", supplier_nif="B11111111",
            invoice_date="01/03/2026", total="100,00"))
        payload = res.to_dict()
        json.dumps(payload)
        assert payload["strategy"] == "order_code"
        assert payload["needs_review"] is False

    def test_anything_not_from_the_code_needs_review(self, resolver):
        res = resolver.resolve(InvoiceSignals(
            supplier_nif="B11111111", invoice_date="01/03/2026", total="100,00"))
        assert res.needs_review is True


class TestIndex:
    def test_duplicate_order_ids_are_recorded_not_silently_dropped(self):
        index = ErpIndex([
            make_entry("PO-2026-0001", entry_id="AS-1"),
            make_entry("PO-2026-0001", entry_id="AS-2"),
        ])
        assert index.duplicate_order_ids == ["PO-2026-0001"]
        assert len(index) == 1

    def test_entries_without_an_order_are_skipped(self):
        index = ErpIndex([make_entry("PO-2026-0001"), {"entry_id": "AS-9", "order_id": ""}])
        assert len(index) == 1


# --------------------------------------------------------------------------
# Regression against the real data
# --------------------------------------------------------------------------

#: The regression suite below replays the real 500-invoice corpus. It needs
#: three things that are not in the repository, because they are either
#: challenge data or a throwaway stand-in:
#:
#:   data/erp_entries.jsonl        <- produced by erp_client.py
#:   data/invoices_extracted.jsonl <- produced by tools/extract_invoices.py
#:   fake_ocr.py                   <- stand-in for the OCR layer
#:
#: Without them these tests skip. Every other test in this file runs on
#: order_resolver alone and needs nothing.
needs_corpus = pytest.mark.skipif(
    not (ERP_SNAPSHOT.exists() and INVOICES.exists() and signals_from_raw_text),
    reason="corpus fixtures or the OCR stand-in are not available",
)


def _load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


@pytest.fixture(scope="module")
def corpus():
    return ErpIndex(_load(ERP_SNAPSHOT)), _load(INVOICES)


def _scoreable(records, index):
    for record in records:
        codes = record.get("orders_canonical") or []
        if codes and index.by_order(codes[0]) is not None:
            yield record, codes[0]


@needs_corpus
class TestRealCorpus:
    def test_snapshot_loads_straight_from_file(self):
        index = ErpIndex.from_jsonl(ERP_SNAPSHOT)
        assert len(index) == 516

    def test_the_erp_has_no_duplicate_orders(self, corpus):
        index, _ = corpus
        assert index.duplicate_order_ids == []

    def test_every_erp_order_is_canonical(self, corpus):
        index, _ = corpus
        for entry in index.entries:
            assert find_order_codes(entry.order_id) == [entry.order_id]

    def test_with_the_code_everything_resolves_exactly(self, corpus):
        index, records = corpus
        resolver = OrderResolver(index)
        checked = 0
        for record, truth in _scoreable(records, index):
            result = resolver.resolve(signals_from_raw_text(
                record["text"], purchase_order=truth, blind=False))
            assert result.order_id == truth, record["file"]
            assert result.strategy is Strategy.ORDER_CODE
            checked += 1
        assert checked == 468

    def test_without_the_code_it_never_answers_wrongly(self, corpus):
        """The guarantee we actually care about: no false positives."""
        index, records = corpus
        resolver = OrderResolver(index)
        resolved = escalated = 0
        for record, truth in _scoreable(records, index):
            result = resolver.resolve(signals_from_raw_text(
                record["text"], purchase_order=truth, blind=True))
            if result.resolved:
                assert result.order_id == truth, f"false positive on {record['file']}"
                resolved += 1
            else:
                escalated += 1
                # An escalation is only useful if the answer is in the shortlist.
                assert truth in {c.order_id for c in result.candidates}, record["file"]
        assert resolved >= 450
        assert resolved + escalated == 468

    def test_escalation_shortlists_stay_short(self, corpus):
        index, records = corpus
        resolver = OrderResolver(index)
        for record, truth in _scoreable(records, index):
            result = resolver.resolve(signals_from_raw_text(
                record["text"], purchase_order=truth, blind=True))
            if not result.resolved:
                assert len(result.candidates) <= 5, record["file"]

    def test_tampered_amounts_are_still_found_and_still_flagged(self, corpus):
        """Finding the entry must never hide the discrepancy."""
        index, records = corpus
        resolver = OrderResolver(index)
        flagged = 0
        for record, truth in _scoreable(records, index):
            entry = index.by_order(truth)
            result = resolver.resolve(signals_from_raw_text(
                record["text"], purchase_order=truth, blind=False))
            total = normalise_amount(signals_from_raw_text(record["text"]).total)
            if total is None or total == entry.amount_cents:
                continue
            assert result.order_id == truth
            assert Anomaly.AMOUNT_MISMATCH.value in result.anomalies
            flagged += 1
        assert flagged >= 9

