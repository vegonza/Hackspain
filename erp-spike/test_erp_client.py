#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test suite for erp_client.

Two layers:

  1. Pure-function tests. No network, instant, exhaustive. These cover the
     parsers, which is where the only money-corrupting bug lived.

  2. Stub-server tests. A real HTTP server is started on a free loopback
     port and configured to reproduce every failure mode of the legacy ERP,
     plus several the real ERP has not shown us yet but that the Saturday
     batch could introduce: malformed XML, truncated bodies, missing
     elements, corrupt dates and amounts, duplicate ids, mid-dump drift.

Run with:
    python3 -m unittest -v test_erp_client
    python3 test_erp_client.py
"""

from __future__ import annotations

import http.server
import json
import os
import tempfile
import threading
import time
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import erp_client
from erp_client import (
    Entry,
    ErpClient,
    ErpPermanentError,
    ErpProtocolError,
    ErpUnavailable,
    build_diagnostics,
    find_id_gaps,
    parse_legacy_amount,
    parse_legacy_date,
    write_jsonl_atomically,
)


# ===========================================================================
# Layer 1 - pure functions
# ===========================================================================

class TestAmountParsing(unittest.TestCase):
    """The single most dangerous function in the client.

    The bridge normally emits Spanish grouping, but echoes the raw source
    value when its own formatting fails, and the source uses English
    decimals. Stripping dots unconditionally multiplied money by 100.
    """

    def test_spanish_grouped(self):
        value, warning = parse_legacy_amount("12.874,40")
        self.assertEqual(value, Decimal("12874.40"))
        self.assertIsNone(warning)

    def test_spanish_plain_decimal(self):
        value, warning = parse_legacy_amount("524,98")
        self.assertEqual(value, Decimal("524.98"))
        self.assertIsNone(warning)

    def test_spanish_multiple_groups(self):
        self.assertEqual(parse_legacy_amount("1.234.567,89")[0], Decimal("1234567.89"))

    def test_english_decimal_is_not_multiplied(self):
        """Regression test for audit finding C-1."""
        value, warning = parse_legacy_amount("1234.56")
        self.assertEqual(value, Decimal("1234.56"))
        self.assertNotEqual(value, Decimal("123456"))
        self.assertEqual(warning, "amount_english_format")

    def test_english_single_decimal_digit(self):
        self.assertEqual(parse_legacy_amount("1234.5")[0], Decimal("1234.5"))

    def test_english_cents_only(self):
        self.assertEqual(parse_legacy_amount("0.99")[0], Decimal("0.99"))

    def test_english_mixed_separators(self):
        value, warning = parse_legacy_amount("1,234.56")
        self.assertEqual(value, Decimal("1234.56"))
        self.assertEqual(warning, "amount_english_format")

    def test_english_grouping_only(self):
        self.assertEqual(parse_legacy_amount("1,234,567")[0], Decimal("1234567"))

    def test_ambiguous_three_digit_fraction_is_flagged(self):
        """'1.234' could be 1234 or 1.234. We pick the Spanish reading and
        say so, instead of guessing in silence."""
        value, warning = parse_legacy_amount("1.234")
        self.assertEqual(value, Decimal("1234"))
        self.assertEqual(warning, "amount_ambiguous_thousands")

    def test_ambiguous_comma_three_digits_is_flagged(self):
        value, warning = parse_legacy_amount("1,234")
        self.assertEqual(value, Decimal("1.234"))
        self.assertEqual(warning, "amount_ambiguous_thousands")

    def test_plain_integer(self):
        self.assertEqual(parse_legacy_amount("1234")[0], Decimal("1234"))

    def test_zero(self):
        self.assertEqual(parse_legacy_amount("0")[0], Decimal("0"))

    def test_negative(self):
        self.assertEqual(parse_legacy_amount("-12.874,40")[0], Decimal("-12874.40"))

    def test_explicit_positive(self):
        self.assertEqual(parse_legacy_amount("+524,98")[0], Decimal("524.98"))

    def test_whitespace_and_nbsp(self):
        self.assertEqual(parse_legacy_amount("  12.874,40 ")[0], Decimal("12874.40"))
        self.assertEqual(parse_legacy_amount("12.874,40\u00a0")[0], Decimal("12874.40"))

    def test_empty_is_none_without_warning(self):
        value, warning = parse_legacy_amount("")
        self.assertIsNone(value)
        self.assertIsNone(warning)

    def test_malformed_grouping_is_rejected(self):
        """Regression test: groups must be exactly three digits. Otherwise
        '12,34,56' was silently read as 123456."""
        for corrupt in ("12,34,56", "1.23.456", "1..2", "1,,2", "12.3456.789"):
            with self.subTest(corrupt=corrupt):
                value, warning = parse_legacy_amount(corrupt)
                self.assertIsNone(value, f"{corrupt!r} must not parse")
                self.assertTrue(warning and warning.startswith("amount_unparseable"))

    def test_garbage_is_flagged(self):
        for garbage in ("N/A", "pendiente", "--5", "EUR50", "1e10", "..", ",,"):
            with self.subTest(garbage=garbage):
                value, warning = parse_legacy_amount(garbage)
                self.assertIsNone(value, f"{garbage!r} should not parse")
                self.assertIsNotNone(warning)

    def test_never_raises(self):
        for hostile in ("", " ", ",", ".", "-", "+", "," * 500, "9" * 5000, "\x00",
                        "1" + "." * 100 + "2", "\u00a0", "1,2.3,4.5"):
            with self.subTest(hostile=hostile[:20]):
                parse_legacy_amount(hostile)

    def test_precision_is_exact(self):
        """Decimal, not float: 0.1 + 0.2 must be 0.3 for a 0.01 tolerance
        comparison to mean anything."""
        a = parse_legacy_amount("0,10")[0]
        b = parse_legacy_amount("0,20")[0]
        self.assertEqual(a + b, Decimal("0.30"))

    def test_large_amount(self):
        self.assertEqual(parse_legacy_amount("999.999.999,99")[0], Decimal("999999999.99"))


class TestDateParsing(unittest.TestCase):
    def test_legacy_format(self):
        value, warning = parse_legacy_date("21/03/2026")
        self.assertEqual(value, date(2026, 3, 21))
        self.assertIsNone(warning)

    def test_iso_fallback_is_accepted_and_flagged(self):
        value, warning = parse_legacy_date("2026-03-21")
        self.assertEqual(value, date(2026, 3, 21))
        self.assertEqual(warning, "date_in_iso_format")

    def test_day_month_are_not_swapped(self):
        """01/02/2026 is 1 February, not 2 January."""
        self.assertEqual(parse_legacy_date("01/02/2026")[0], date(2026, 2, 1))

    def test_leap_day(self):
        self.assertEqual(parse_legacy_date("29/02/2024")[0], date(2024, 2, 29))

    def test_invalid_leap_day(self):
        self.assertIsNone(parse_legacy_date("29/02/2026")[0])

    def test_impossible_dates(self):
        for bad in ("31/02/2026", "32/01/2026", "01/13/2026", "00/01/2026"):
            with self.subTest(bad=bad):
                self.assertIsNone(parse_legacy_date(bad)[0])

    def test_out_of_range_year_is_rejected(self):
        value, warning = parse_legacy_date("21/03/1200")
        self.assertIsNone(value)
        self.assertIn("out_of_range", warning)

    def test_empty(self):
        value, warning = parse_legacy_date("")
        self.assertIsNone(value)
        self.assertIsNone(warning)

    def test_never_raises(self):
        for hostile in ("", "//", "aa/bb/cccc", "2026", "\x00", "1" * 1000, "1/1/1"):
            with self.subTest(hostile=hostile[:20]):
                parse_legacy_date(hostile)


class TestGapDetection(unittest.TestCase):
    def test_simple_gap(self):
        self.assertEqual(find_id_gaps(["AS-00001", "AS-00003"]), ["AS-00002"])

    def test_multiple_missing(self):
        self.assertEqual(find_id_gaps(["AS-70007", "AS-70010"]), ["AS-70008", "AS-70009"])

    def test_no_gap(self):
        self.assertEqual(find_id_gaps(["AS-00001", "AS-00002", "AS-00003"]), [])

    def test_series_change_is_not_a_gap(self):
        """AS-00518 -> AS-70001 is a different series, not 69 482 holes."""
        self.assertEqual(find_id_gaps(["AS-00518", "AS-70001"]), [])

    def test_real_world_holes(self):
        ids = ["AS-70006", "AS-70007", "AS-70009", "AS-70010",
               "AS-72003", "AS-72005", "AS-72007"]
        self.assertEqual(find_id_gaps(ids), ["AS-70008", "AS-72004", "AS-72006"])

    def test_unparseable_ids_are_ignored(self):
        self.assertEqual(find_id_gaps(["", "weird", "AS-00001", "AS-00002"]), [])

    def test_order_does_not_matter(self):
        self.assertEqual(find_id_gaps(["AS-00003", "AS-00001"]), ["AS-00002"])

    def test_duplicates_do_not_create_gaps(self):
        self.assertEqual(find_id_gaps(["AS-1", "AS-1", "AS-2"]), [])


class TestEntryNormalization(unittest.TestCase):
    @staticmethod
    def _xml(**overrides):
        fields = {
            "id": "AS-00084", "fecha": "21/03/2026", "proveedor": "P002",
            "nif": "A41220987", "pedido": "PO-2026-0084",
            "importe": "6.199,54", "estado": "PENDIENTE",
        }
        fields.update(overrides)
        inner = "".join(f"<{k}>{v}</{k}>" for k, v in fields.items())
        return erp_client.ElementTree.fromstring(f"<asiento>{inner}</asiento>")

    def test_clean_entry_has_no_warnings(self):
        entry = Entry.from_xml(self._xml())
        self.assertEqual(entry.warnings, [])
        self.assertEqual(entry.amount, Decimal("6199.54"))
        self.assertEqual(entry.date, date(2026, 3, 21))

    def test_empty_tax_id_is_flagged(self):
        """Matches the 20 real entries AS-00499..AS-00518."""
        entry = Entry.from_xml(self._xml(nif=""))
        self.assertIn("empty_field:tax_id", entry.warnings)

    def test_unknown_status_is_flagged(self):
        entry = Entry.from_xml(self._xml(estado="ANULADA"))
        self.assertIn("unknown_status:'ANULADA'", entry.warnings)

    def test_character_loss_is_flagged(self):
        entry = Entry.from_xml(self._xml(proveedor="P0?2"))
        self.assertIn("possible_character_loss", entry.warnings)

    def test_corrupt_amount_is_flagged_not_fatal(self):
        entry = Entry.from_xml(self._xml(importe="importe pendiente"))
        self.assertIsNone(entry.amount)
        self.assertEqual(entry.raw_amount, "importe pendiente")
        self.assertTrue(any(w.startswith("amount_") for w in entry.warnings))

    def test_raw_values_are_always_preserved(self):
        entry = Entry.from_xml(self._xml(importe="1234.56", fecha="2026-03-21"))
        self.assertEqual(entry.raw_amount, "1234.56")
        self.assertEqual(entry.raw_date, "2026-03-21")

    def test_missing_elements_do_not_crash(self):
        node = erp_client.ElementTree.fromstring("<asiento><id>AS-1</id></asiento>")
        entry = Entry.from_xml(node)
        self.assertEqual(entry.entry_id, "AS-1")
        self.assertIn("empty_field:tax_id", entry.warnings)

    def test_completely_empty_node(self):
        node = erp_client.ElementTree.fromstring("<asiento/>")
        entry = Entry.from_xml(node)
        self.assertEqual(len(entry.warnings), 5)

    def test_serialization_keeps_decimal_precision(self):
        entry = Entry.from_xml(self._xml(importe="0,10"))
        self.assertEqual(entry.to_dict()["amount"], "0.10")
        self.assertIsInstance(entry.to_dict()["amount"], str)

    def test_serialization_is_json_safe(self):
        entry = Entry.from_xml(self._xml(proveedor="P&lt;0&gt;2"))
        json.dumps(entry.to_dict())  # must not raise


class TestDiagnostics(unittest.TestCase):
    @staticmethod
    def _entry(entry_id="AS-1", order_id="PO-1", status="PENDIENTE"):
        return Entry(
            entry_id=entry_id, supplier_id="P001", tax_id="B1", order_id=order_id,
            status=status, raw_date="", raw_amount="",
        )

    def test_complete_snapshot(self):
        entries = [self._entry("AS-00001", "PO-1"), self._entry("AS-00002", "PO-2")]
        status = {"entry_count": 2, "update_loaded": False}
        self.assertTrue(build_diagnostics(entries, 2, status, status)["complete"])

    def test_missing_entries_marks_incomplete(self):
        entries = [self._entry("AS-00001", "PO-1")]
        status = {"entry_count": 2, "update_loaded": False}
        self.assertFalse(build_diagnostics(entries, 2, status, status)["complete"])

    def test_mid_dump_reload_is_detected(self):
        entries = [self._entry()]
        before = {"entry_count": 1, "update_loaded": False}
        after = {"entry_count": 41, "update_loaded": True}
        diagnostics = build_diagnostics(entries, 1, before, after)
        self.assertTrue(diagnostics["snapshot_drift"])
        self.assertFalse(diagnostics["complete"])

    def test_duplicate_order_ids_are_reported(self):
        """Two entries for one order is the double-payment scenario."""
        entries = [self._entry("AS-1", "PO-9"), self._entry("AS-2", "PO-9")]
        status = {"entry_count": 2, "update_loaded": False}
        self.assertEqual(
            build_diagnostics(entries, 2, status, status)["duplicate_order_ids"], ["PO-9"]
        )

    def test_duplicate_entry_ids_are_reported(self):
        entries = [self._entry("AS-1", "PO-1"), self._entry("AS-1", "PO-2")]
        status = {"entry_count": 2, "update_loaded": False}
        self.assertEqual(
            build_diagnostics(entries, 2, status, status)["duplicate_entry_ids"], ["AS-1"]
        )

    def test_empty_snapshot_is_never_complete(self):
        status = {"entry_count": 0, "update_loaded": False}
        self.assertFalse(build_diagnostics([], 0, status, status)["complete"])

    def test_status_counts(self):
        entries = [self._entry("AS-1", "PO-1", "PENDIENTE"),
                   self._entry("AS-2", "PO-2", "PAGADA")]
        status = {"entry_count": 2, "update_loaded": False}
        counts = build_diagnostics(entries, 2, status, status)["status_counts"]
        self.assertEqual(counts, {"PENDIENTE": 1, "PAGADA": 1})


class TestAtomicWrite(unittest.TestCase):
    @staticmethod
    def _entries(count):
        return [Entry(f"AS-{i}", "P1", "B1", f"PO-{i}", "PENDIENTE", "", "")
                for i in range(count)]

    def test_writes_all_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "nested" / "out.jsonl"
            write_jsonl_atomically(self._entries(5), target)
            lines = target.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 5)
        self.assertEqual(json.loads(lines[0])["entry_id"], "AS-0")

    def test_no_temporary_files_are_left_behind(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "out.jsonl"
            write_jsonl_atomically(self._entries(1), target)
            self.assertEqual([p.name for p in Path(tmp).iterdir()], ["out.jsonl"])

    def test_overwrite_is_atomic(self):
        older = [Entry("AS-OLD", "P1", "B1", "PO-1", "PENDIENTE", "", "")]
        newer = [Entry("AS-NEW", "P1", "B1", "PO-1", "PENDIENTE", "", "")]
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "out.jsonl"
            write_jsonl_atomically(older, target)
            write_jsonl_atomically(newer, target)
            content = target.read_text(encoding="utf-8")
        self.assertIn("AS-NEW", content)
        self.assertNotIn("AS-OLD", content)

    def test_every_line_is_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "out.jsonl"
            write_jsonl_atomically(self._entries(20), target)
            for line in target.read_text(encoding="utf-8").splitlines():
                json.loads(line)


class TestPathSafety(unittest.TestCase):
    def test_path_traversal_is_rejected(self):
        client = ErpClient(base_url="http://127.0.0.1:1")
        for hostile in ("../../etc/passwd", "AS-1/../../x", "AS 1", "", "a" * 100,
                        "AS-1?token=x", "AS-1#frag", "AS-1\n"):
            with self.subTest(hostile=hostile):
                with self.assertRaises(ErpPermanentError):
                    client.entry(hostile)

    def test_legitimate_ids_are_accepted(self):
        from erp_client import _encode_path_segment
        self.assertEqual(_encode_path_segment("AS-00084"), "AS-00084")

    def test_invalid_base_url_is_rejected(self):
        for bad in ("", "not-a-url", "ftp://x", "file:///etc/passwd", "javascript:alert(1)"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    ErpClient(base_url=bad)

    def test_invalid_rate_is_rejected(self):
        for bad in (0, -1):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    ErpClient(requests_per_second=bad)


# ===========================================================================
# Layer 2 - stub ERP server
# ===========================================================================

def _entry_xml(index: int, **overrides) -> str:
    fields = {
        "id": f"AS-{index:05d}",
        "fecha": "21/03/2026",
        "proveedor": "P002",
        "nif": "A41220987",
        "pedido": f"PO-2026-{index:04d}",
        "importe": "6.199,54",
        "estado": "PENDIENTE",
    }
    fields.update(overrides)
    inner = "".join(f"      <{k}>{v}</{k}>\n" for k, v in fields.items())
    return f"    <asiento>\n{inner}    </asiento>\n"


class StubConfig:
    """Everything the stub can be told to do wrong."""

    def __init__(self):
        self.total_entries = 45          # 3 pages of 20
        self.page_size = 20
        self.fail_every = 0              # ORA-00600 cadence, 0 = never
        self.fail_first_n_authenticated = 0   # consecutive ORA-00600 burst
        self.rate_limit_first_n = 0      # ERP-429 for the first N calls
        self.expire_session_after = 0    # SES-401 on the Nth authenticated call
        self.malformed_xml_on_page = 0
        self.truncated_body_on_page = 0
        self.drop_meta_on_page = 0
        self.redirect_on_status = False
        self.huge_body = False
        self.corrupt_entries = {}        # index -> field overrides
        self.duplicate_entry_id = False
        self.entry_count_after_reload = None
        self.reject_credentials = False
        # Value of the Retry-After header sent with every 429. None means
        # "send no header at all"; the real ERP always sends "1".
        self.retry_after_header = "1"

        # observations
        self.tokens_in_query = 0
        self.tokens_in_header = 0
        self.authenticated_calls = 0
        self.total_calls = 0
        self.login_calls = 0


class _StubHandler(http.server.BaseHTTPRequestHandler):
    config: StubConfig
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # silence the default stderr spam
        pass

    # -- helpers -----------------------------------------------------------

    def _send(self, status, body, content_type="application/xml; charset=ISO-8859-1",
              extra_headers=None):
        payload = body.encode("iso-8859-1", errors="replace")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(payload)

    def _send_error_xml(self, status, code, message, extra_headers=None):
        self._send(status, '<?xml version="1.0" encoding="ISO-8859-1"?>\n'
                           f"<error><codigo>{code}</codigo><mensaje>{message}</mensaje></error>",
                   extra_headers=extra_headers)

    def _send_rate_limited(self):
        """Mirror the real ERP, which answers 429 with a Retry-After header."""
        headers = {}
        if self.config.retry_after_header is not None:
            headers["Retry-After"] = self.config.retry_after_header
        self._send_error_xml(429, "ERP-429", "Demasiadas peticiones.", extra_headers=headers)

    def _token(self, query):
        cfg = self.config
        header = self.headers.get("X-ERP-Token")
        if header:
            cfg.tokens_in_header += 1
            return header
        values = query.get("token")
        if values:
            cfg.tokens_in_query += 1
            return values[0]
        return None

    # -- endpoints ---------------------------------------------------------

    def do_POST(self):  # noqa: N802
        cfg = self.config
        cfg.total_calls += 1
        cfg.login_calls += 1

        if cfg.rate_limit_first_n and cfg.total_calls <= cfg.rate_limit_first_n:
            self._send_rate_limited()
            return
        if cfg.reject_credentials:
            self._send_error_xml(401, "SES-401", "Credenciales no reconocidas.")
            return

        self._send(200, '<?xml version="1.0" encoding="ISO-8859-1"?>\n'
                        f"<sesion><token>tok{cfg.login_calls:04d}</token>"
                        "<caduca_en_segundos>900</caduca_en_segundos>"
                        "<usos_maximos>300</usos_maximos></sesion>")

    def do_GET(self):  # noqa: N802
        cfg = self.config
        cfg.total_calls += 1
        url = urlparse(self.path)
        query = parse_qs(url.query)

        if cfg.rate_limit_first_n and cfg.total_calls <= cfg.rate_limit_first_n:
            self._send_rate_limited()
            return

        if url.path == "/erp/estado":
            if cfg.redirect_on_status:
                self.send_response(302)
                self.send_header("Location", "http://example.invalid/stolen")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if cfg.huge_body:
                self._send(200, "x" * 200_000)
                return
            count, loaded = cfg.total_entries, "NO"
            if cfg.entry_count_after_reload is not None and cfg.authenticated_calls > 0:
                count, loaded = cfg.entry_count_after_reload, "SI"
            self._send(200, '<?xml version="1.0" encoding="ISO-8859-1"?>\n'
                            "<estado><version>stub 1.0</version>"
                            "<activo_segundos>1</activo_segundos>"
                            f"<asientos>{count}</asientos>"
                            f"<actualizacion_cargada>{loaded}</actualizacion_cargada></estado>")
            return

        if not url.path.startswith("/erp/asientos"):
            self._send_error_xml(404, "ERP-404", "Recurso no encontrado.")
            return

        # ---- authentication -------------------------------------------
        if not self._token(query):
            self._send_error_xml(401, "SES-401", "Sesion no valida.")
            return
        cfg.authenticated_calls += 1
        if cfg.expire_session_after and cfg.authenticated_calls == cfg.expire_session_after:
            self._send_error_xml(401, "SES-401", "Sesion caducada.")
            return

        # ---- injected faults ------------------------------------------
        if cfg.authenticated_calls <= cfg.fail_first_n_authenticated:
            self._send_error_xml(500, "ORA-00600", "Error interno del nucleo.")
            return
        if cfg.fail_every and cfg.authenticated_calls % cfg.fail_every == 0:
            self._send_error_xml(500, "ORA-00600", "Error interno del nucleo.")
            return

        # ---- detail ----------------------------------------------------
        if url.path.rstrip("/") != "/erp/asientos":
            entry_id = url.path.rsplit("/", 1)[-1]
            if not entry_id.startswith("AS-"):
                self._send_error_xml(404, "ERP-404", f"El asiento {entry_id} no consta.")
                return
            self._send(200, '<?xml version="1.0" encoding="ISO-8859-1"?>\n<respuesta>\n'
                            "  <asientos>\n" + _entry_xml(1) + "  </asientos>\n</respuesta>\n")
            return

        # ---- listing ----------------------------------------------------
        try:
            page = int((query.get("pagina") or ["1"])[0])
        except ValueError:
            self._send_error_xml(400, "ERP-400", "Parametro pagina invalido.")
            return

        pages = max(1, (cfg.total_entries + cfg.page_size - 1) // cfg.page_size)
        if page < 1 or page > pages:
            self._send_error_xml(400, "ERP-400", f"Pagina fuera de rango: {page}.")
            return

        if page == cfg.malformed_xml_on_page:
            self._send(200, "<respuesta><meta><total>oops")
            return
        if page == cfg.truncated_body_on_page:
            self._send(200, '<?xml version="1.0" encoding="ISO-8859-1"?>\n<respuesta>\n  <asien')
            return

        first = (page - 1) * cfg.page_size
        last = min(first + cfg.page_size, cfg.total_entries)
        rows = []
        for index in range(first, last):
            overrides = cfg.corrupt_entries.get(index, {})
            if cfg.duplicate_entry_id and index == last - 1 and first > 0:
                overrides = dict(overrides, id="AS-00000")
            rows.append(_entry_xml(index, **overrides))

        meta = ""
        if page != cfg.drop_meta_on_page:
            meta = ("  <meta>\n"
                    f"    <total>{cfg.total_entries}</total>\n"
                    f"    <paginas>{pages}</paginas>\n"
                    f"    <pagina>{page}</pagina>\n"
                    f"    <por_pagina>{cfg.page_size}</por_pagina>\n"
                    "  </meta>\n")

        self._send(200, '<?xml version="1.0" encoding="ISO-8859-1"?>\n<respuesta>\n'
                        + meta + "  <asientos>\n" + "".join(rows)
                        + "  </asientos>\n</respuesta>\n")


class StubServerTestCase(unittest.TestCase):
    """Base class that starts a configurable stub ERP on a free port."""

    def setUp(self):
        self.config = StubConfig()
        handler = type("BoundHandler", (_StubHandler,), {"config": self.config})
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def client(self, **kwargs):
        # Timing parameters are collapsed so the suite runs in seconds. They
        # are injected rather than patched, which is why they are
        # constructor arguments in the first place.
        kwargs.setdefault("requests_per_second", 500.0)
        kwargs.setdefault("rate_limit_cooldown_seconds", 0.01)
        kwargs.setdefault("backoff_base_seconds", 0.01)
        kwargs.setdefault("backoff_cap_seconds", 0.05)
        return ErpClient(base_url=self.base_url, **kwargs)


class TestHappyPath(StubServerTestCase):
    def test_status(self):
        status = self.client().status()
        self.assertEqual(status["entry_count"], 45)
        self.assertFalse(status["update_loaded"])
        self.assertEqual(status["version"], "stub 1.0")

    def test_full_snapshot(self):
        snapshot = self.client().snapshot()
        self.assertEqual(len(snapshot.entries), 45)
        self.assertTrue(snapshot.complete)
        self.assertEqual(snapshot.diagnostics["duplicate_entry_ids"], [])

    def test_single_login_for_whole_dump(self):
        client = self.client()
        client.snapshot()
        self.assertEqual(client.metrics.logins, 1)

    def test_no_retries_on_a_healthy_server(self):
        client = self.client()
        client.snapshot()
        self.assertEqual(client.metrics.total_retries, 0)

    def test_report_is_serializable(self):
        json.dumps(self.client().snapshot().report())

    def test_index_by_order_id(self):
        index = self.client().snapshot().by_order_id()
        self.assertIn("PO-2026-0000", index)

    def test_detail_lookup(self):
        entry = self.client().entry("AS-00001")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.supplier_id, "P002")

    def test_unknown_entry_returns_none(self):
        self.assertIsNone(self.client().entry("XX-00001"))

    def test_single_page_dataset(self):
        self.config.total_entries = 5
        snapshot = self.client().snapshot()
        self.assertEqual(len(snapshot.entries), 5)
        self.assertTrue(snapshot.complete)

    def test_exact_page_boundary(self):
        self.config.total_entries = 40
        snapshot = self.client().snapshot()
        self.assertEqual(len(snapshot.entries), 40)
        self.assertTrue(snapshot.complete)


class TestInjectedFaults(StubServerTestCase):
    def test_ora00600_is_absorbed(self):
        self.config.total_entries = 200          # 10 pages, so the 10th query lands
        self.config.fail_every = 10
        client = self.client()
        snapshot = client.snapshot()
        self.assertEqual(len(snapshot.entries), 200)
        self.assertTrue(snapshot.complete)
        self.assertGreater(client.metrics.retries_ora00600, 0)

    def test_aggressive_fault_rate_still_completes(self):
        """Every third query fails, a far harsher cadence than the real ERP."""
        self.config.fail_every = 3
        snapshot = self.client().snapshot()
        self.assertEqual(len(snapshot.entries), 45)
        self.assertTrue(snapshot.complete)

    def test_consecutive_faults_are_survived(self):
        """The real ERP never fails twice in a row for a sequential client,
        but the Saturday build might. Three in a row must still recover."""
        self.config.fail_first_n_authenticated = 3
        client = self.client()
        snapshot = client.snapshot()
        self.assertTrue(snapshot.complete)
        self.assertEqual(client.metrics.retries_ora00600, 3)

    def test_faults_beyond_the_attempt_budget_give_up_cleanly(self):
        self.config.fail_first_n_authenticated = 99
        client = self.client(max_attempts=3)
        with self.assertRaises(ErpUnavailable):
            client.snapshot()

    def test_rate_limit_is_absorbed(self):
        self.config.rate_limit_first_n = 3
        client = self.client()
        snapshot = client.snapshot()
        self.assertTrue(snapshot.complete)
        self.assertGreaterEqual(client.metrics.retries_rate_limited, 1)

    def test_rate_limited_login_is_retried(self):
        """Regression test for audit finding C-2: version 1 aborted the whole
        run if the login itself was throttled."""
        self.config.rate_limit_first_n = 2
        client = self.client()
        client.ensure_session()
        self.assertEqual(client.metrics.logins, 1)
        self.assertGreaterEqual(client.metrics.retries_rate_limited, 1)

    def test_rate_limited_status_is_retried(self):
        """Regression test for audit finding C-3."""
        self.config.rate_limit_first_n = 2
        client = self.client()
        self.assertEqual(client.status()["entry_count"], 45)
        self.assertGreaterEqual(client.metrics.retries_rate_limited, 1)

    def test_session_expiry_triggers_relogin(self):
        self.config.expire_session_after = 2
        client = self.client()
        snapshot = client.snapshot()
        self.assertTrue(snapshot.complete)
        self.assertEqual(client.metrics.retries_session_expired, 1)
        self.assertEqual(client.metrics.logins, 2)

    def test_bad_credentials_fail_fast(self):
        self.config.reject_credentials = True
        client = self.client()
        self.assertEqual(client.status()["entry_count"], 45)  # anonymous still works
        with self.assertRaises(ErpPermanentError):
            client.page(1)
        self.assertEqual(client.metrics.logins, 0)


class TestMalformedResponses(StubServerTestCase):
    def test_malformed_xml_is_retried_then_reported(self):
        self.config.malformed_xml_on_page = 2
        client = self.client(max_attempts=3)
        with self.assertRaises(ErpUnavailable):
            client.snapshot()
        self.assertEqual(client.metrics.retries_protocol, 3)

    def test_truncated_body_is_retried_then_reported(self):
        self.config.truncated_body_on_page = 2
        with self.assertRaises(ErpUnavailable):
            self.client(max_attempts=3).snapshot()

    def test_missing_meta_block_is_retried_then_reported(self):
        self.config.drop_meta_on_page = 1
        with self.assertRaises(ErpUnavailable):
            self.client(max_attempts=3).snapshot()

    def test_transient_malformed_response_recovers(self):
        """A dropped connection on one attempt must not kill the dump."""
        self.config.malformed_xml_on_page = 2
        client = self.client(max_attempts=5)

        original = client._send
        state = {"seen": 0}

        def flaky(method, path, params=None, form=None, token=None):
            # Heal the stub after the first bad page so the retry succeeds.
            if params and params.get("pagina") == 2:
                state["seen"] += 1
                if state["seen"] > 1:
                    self.config.malformed_xml_on_page = 0
            return original(method, path, params=params, form=form, token=token)

        client._send = flaky
        snapshot = client.snapshot()
        self.assertTrue(snapshot.complete)
        self.assertGreaterEqual(client.metrics.retries_protocol, 1)

    def test_out_of_range_page_is_permanent(self):
        with self.assertRaises(ErpPermanentError) as ctx:
            self.client().page(999)
        self.assertEqual(ctx.exception.code, "ERP-400")

    def test_page_zero_is_rejected_client_side(self):
        client = self.client()
        with self.assertRaises(ErpPermanentError):
            client.page(0)
        self.assertEqual(client.metrics.requests, 0, "must not hit the network")


class TestDataQualityDetection(StubServerTestCase):
    def test_corrupt_amount_is_flagged_not_fatal(self):
        self.config.corrupt_entries = {5: {"importe": "no disponible"}}
        snapshot = self.client().snapshot()
        self.assertTrue(snapshot.complete)
        flagged = [e for e in snapshot.entries
                   if any(w.startswith("amount_") for w in e.warnings)]
        self.assertEqual(len(flagged), 1)
        self.assertEqual(flagged[0].raw_amount, "no disponible")

    def test_english_amount_is_not_multiplied_end_to_end(self):
        """The full-pipeline version of audit finding C-1."""
        self.config.corrupt_entries = {7: {"importe": "1234.56"}}
        snapshot = self.client().snapshot()
        entry = snapshot.entries[7]
        self.assertEqual(entry.amount, Decimal("1234.56"))
        self.assertIn("amount_english_format", entry.warnings)

    def test_empty_tax_id_is_flagged(self):
        self.config.corrupt_entries = {3: {"nif": ""}}
        snapshot = self.client().snapshot()
        self.assertEqual(snapshot.diagnostics["warning_counts"].get("empty_field"), 1)

    def test_iso_date_is_recovered(self):
        self.config.corrupt_entries = {2: {"fecha": "2026-07-15"}}
        snapshot = self.client().snapshot()
        self.assertEqual(snapshot.entries[2].date, date(2026, 7, 15))

    def test_duplicate_entry_ids_are_reported(self):
        self.config.duplicate_entry_id = True
        snapshot = self.client().snapshot()
        self.assertTrue(snapshot.diagnostics["duplicate_entry_ids"])

    def test_unknown_status_is_flagged(self):
        self.config.corrupt_entries = {1: {"estado": "ANULADA"}}
        snapshot = self.client().snapshot()
        self.assertEqual(snapshot.diagnostics["warning_counts"].get("unknown_status"), 1)

    def test_mid_dump_reload_is_caught(self):
        self.config.entry_count_after_reload = 85
        snapshot = self.client().snapshot()
        self.assertTrue(snapshot.diagnostics["snapshot_drift"])
        self.assertFalse(snapshot.complete)

    def test_dump_command_fails_on_drift(self):
        """The exit code is what stops a Docker pipeline from continuing."""
        import argparse as _argparse
        self.config.entry_count_after_reload = 85
        with tempfile.TemporaryDirectory() as tmp:
            args = _argparse.Namespace(output=str(Path(tmp) / "out.jsonl"), report=None)
            code = erp_client.command_dump(self.client(), args)
        self.assertEqual(code, 1)

    def test_dump_command_succeeds_on_clean_data(self):
        import argparse as _argparse
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "out.jsonl"
            args = _argparse.Namespace(output=str(target), report=str(Path(tmp) / "r.json"))
            code = erp_client.command_dump(self.client(), args)
            self.assertEqual(code, 0)
            self.assertEqual(len(target.read_text(encoding="utf-8").splitlines()), 45)


class TestSecurityPosture(StubServerTestCase):
    def test_token_never_travels_in_the_query_string(self):
        """Audit finding A-1: the server logs the request line."""
        self.client().snapshot()
        self.assertEqual(self.config.tokens_in_query, 0)
        self.assertGreater(self.config.tokens_in_header, 0)

    def test_redirects_are_refused(self):
        """Audit finding A-3: following a 3xx would replay the token against
        whatever host the server names."""
        self.config.redirect_on_status = True
        with self.assertRaises(ErpUnavailable):
            self.client(max_attempts=2).status()

    def test_oversized_responses_are_rejected(self):
        """Audit finding A-4."""
        self.config.huge_body = True
        with self.assertRaises(ErpUnavailable):
            self.client(max_attempts=2, max_response_bytes=1000).status()

    def test_normal_responses_pass_the_size_check(self):
        self.assertEqual(self.client(max_response_bytes=1000).status()["entry_count"], 45)

    def test_proxy_environment_is_ignored(self):
        """Audit finding A-2: on a managed laptop http_proxy could route
        loopback traffic, and the login credentials, through a third party."""
        keys = ("http_proxy", "HTTP_PROXY", "ALL_PROXY", "all_proxy")
        saved = {k: os.environ.get(k) for k in keys}
        for key in keys:
            os.environ[key] = "http://127.0.0.1:9"  # a closed port
        try:
            self.assertEqual(self.client().status()["entry_count"], 45)
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_credentials_are_not_logged(self):
        import io
        import contextlib
        buffer = io.StringIO()
        client = self.client(verbose=True)
        with contextlib.redirect_stderr(buffer):
            client.snapshot()
        self.assertNotIn(erp_client.ERP_PASSWORD, buffer.getvalue())
        self.assertNotIn("tok0001", buffer.getvalue())


class TestUnavailability(unittest.TestCase):
    def test_closed_port_gives_a_clean_error(self):
        client = ErpClient(base_url="http://127.0.0.1:1", requests_per_second=500.0,
                           max_attempts=2, backoff_base_seconds=0.01,
                           backoff_cap_seconds=0.02)
        with self.assertRaises(ErpUnavailable):
            client.status()

    def test_time_budget_is_enforced(self):
        client = ErpClient(base_url="http://127.0.0.1:1", requests_per_second=500.0,
                           time_budget_seconds=0.2, backoff_base_seconds=0.05,
                           backoff_cap_seconds=0.1)
        started = time.monotonic()
        with self.assertRaises(ErpUnavailable):
            client.status()
        self.assertLess(time.monotonic() - started, 15.0)


class TestDeterminism(StubServerTestCase):
    """A non-deterministic backend must still produce identical output.

    Both tests use a 200-entry dataset (10 pages) so that the fault cadence
    actually fires. With the default 45 entries the dump is only 3 pages and
    no fault would ever land, which would make the proof vacuous.
    """

    def test_repeated_dumps_are_identical_despite_shifting_faults(self):
        self.config.total_entries = 200
        self.config.fail_every = 7
        outputs = []
        with tempfile.TemporaryDirectory() as tmp:
            for run in range(3):
                snapshot = self.client().snapshot()
                self.assertTrue(snapshot.complete)
                target = Path(tmp) / f"run{run}.jsonl"
                write_jsonl_atomically(snapshot.entries, target)
                outputs.append(target.read_bytes())
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[1], outputs[2])

    def test_fault_positions_really_do_shift(self):
        """Guards the premise of the test above. The stub keeps one global
        counter across clients, exactly like the real ERP, so each run hits
        the faults in different places."""
        self.config.total_entries = 200
        self.config.fail_every = 7

        first = self.client()
        first.snapshot()
        second = self.client()
        second.snapshot()

        self.assertGreater(first.metrics.retries_ora00600, 0)
        self.assertGreater(second.metrics.retries_ora00600, 0)


# ===========================================================================
# Layer 3 - time-dependent behaviour, driven by a fake clock
# ===========================================================================

class FakeClock:
    """A monotonic clock that only moves when we tell it to.

    Sleeping advances it instead of blocking, so a thirteen-minute session
    expiry and a thirty-second rate-limit penalty can both be asserted in
    microseconds. `slept` records every wait so tests can check *how long*
    the client decided to stay off the wire, not merely that it waited.
    """

    def __init__(self, start: float = 10_000.0) -> None:
        self.now = start
        self.slept: "list[float]" = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds

    def advance(self, seconds: float) -> None:
        self.now += seconds

    @property
    def longest_sleep(self) -> float:
        return max(self.slept) if self.slept else 0.0


class TestParseRetryAfter(unittest.TestCase):
    """The header is free information from the server. Version 2.1 threw it
    away, which was harmless only because the ERP happens to send the same
    value as our own cooldown."""

    def test_delta_seconds(self):
        self.assertEqual(erp_client.parse_retry_after("1"), 1.0)
        self.assertEqual(erp_client.parse_retry_after("5"), 5.0)
        self.assertEqual(erp_client.parse_retry_after("  7  "), 7.0)

    def test_zero_is_a_real_answer_not_a_missing_one(self):
        self.assertEqual(erp_client.parse_retry_after("0"), 0.0)

    def test_absent_or_empty_header(self):
        self.assertIsNone(erp_client.parse_retry_after(None))
        self.assertIsNone(erp_client.parse_retry_after(""))
        self.assertIsNone(erp_client.parse_retry_after("   "))

    def test_garbage_is_ignored_rather_than_trusted(self):
        for bad in ("soon", "1s", "-", "NaN", "1.5.2", "∞", "<script>"):
            with self.subTest(bad=bad):
                self.assertIsNone(erp_client.parse_retry_after(bad))

    def test_negative_values_never_produce_a_negative_wait(self):
        self.assertEqual(erp_client.parse_retry_after("-10"), 0.0)

    def test_absurd_values_are_capped(self):
        """A hostile or buggy server must not be able to park us for a day."""
        self.assertEqual(
            erp_client.parse_retry_after("86400"), erp_client.MAX_RETRY_AFTER_SECONDS
        )
        self.assertEqual(
            erp_client.parse_retry_after("999999999999"), erp_client.MAX_RETRY_AFTER_SECONDS
        )

    def test_http_date_form(self):
        """RFC 9110 also allows an absolute date. The ERP does not use it,
        but a proxy in front of it might."""
        seconds = erp_client.parse_retry_after(
            "Wed, 21 Oct 2026 07:28:10 GMT",
            now=1792, )
        self.assertIsNotNone(seconds)

    def test_http_date_in_the_past_is_zero_not_negative(self):
        # 1 Jan 1970 is long gone, so the wait is clamped to zero.
        self.assertEqual(
            erp_client.parse_retry_after("Thu, 01 Jan 1970 00:00:00 GMT"), 0.0
        )

    def test_http_date_is_clamped_to_the_cap(self):
        self.assertEqual(
            erp_client.parse_retry_after("Fri, 01 Jan 2100 00:00:00 GMT"),
            erp_client.MAX_RETRY_AFTER_SECONDS,
        )


class TestRateLimitCooldownPolicy(unittest.TestCase):
    """Floor and ceiling: obey the server when it asks for longer, ignore it
    when it asks for less than our own safety margin."""

    def setUp(self):
        self.client = ErpClient(rate_limit_cooldown_seconds=1.1)

    def test_no_header_falls_back_to_our_own_cooldown(self):
        self.assertEqual(self.client._rate_limit_cooldown(None), 1.1)

    def test_server_asking_for_less_does_not_shorten_our_wait(self):
        """The ERP sends `Retry-After: 1`, but its window is a strict `>`
        over a sliding second. Obeying literally would risk a second 429."""
        self.assertEqual(self.client._rate_limit_cooldown(1.0), 1.1)
        self.assertEqual(self.client._rate_limit_cooldown(0.0), 1.1)

    def test_server_asking_for_more_is_obeyed(self):
        self.assertEqual(self.client._rate_limit_cooldown(11.0), 11.0)

    def test_the_cap_is_applied_before_we_ever_see_the_value(self):
        capped = erp_client.parse_retry_after("100000")
        self.assertEqual(
            self.client._rate_limit_cooldown(capped), erp_client.MAX_RETRY_AFTER_SECONDS
        )


class TestRetryAfterIsHonoured(StubServerTestCase):
    """End to end: what the server puts in the header is what we wait."""

    def fake_client(self, clock, **kwargs):
        kwargs.setdefault("requests_per_second", 500.0)
        kwargs.setdefault("rate_limit_cooldown_seconds", 1.1)
        kwargs.setdefault("backoff_base_seconds", 0.01)
        kwargs.setdefault("backoff_cap_seconds", 0.05)
        # The fake clock jumps minutes at a time; a realistic budget would
        # fire spuriously.
        kwargs.setdefault("time_budget_seconds", 100_000.0)
        return ErpClient(base_url=self.base_url, clock=clock, sleeper=clock.sleep, **kwargs)

    def test_a_longer_retry_after_is_obeyed(self):
        """The scenario that motivated this: Saturday's ERP raises the
        penalty to 11 s. Version 2.1 would have waited 1.1 s and been
        throttled again."""
        self.config.rate_limit_first_n = 1
        self.config.retry_after_header = "11"
        clock = FakeClock()
        client = self.fake_client(clock)

        self.assertEqual(client.status()["entry_count"], 45)
        self.assertEqual(client.metrics.retries_rate_limited, 1)
        self.assertGreaterEqual(clock.longest_sleep, 11.0)

    def test_the_servers_own_value_of_one_is_floored_by_our_margin(self):
        self.config.rate_limit_first_n = 1
        self.config.retry_after_header = "1"
        clock = FakeClock()
        client = self.fake_client(clock)

        client.status()
        self.assertGreaterEqual(clock.longest_sleep, 1.1)
        self.assertLess(clock.longest_sleep, 2.0)

    def test_a_missing_header_falls_back_to_our_cooldown(self):
        self.config.rate_limit_first_n = 1
        self.config.retry_after_header = None
        clock = FakeClock()
        client = self.fake_client(clock)

        client.status()
        self.assertGreaterEqual(clock.longest_sleep, 1.1)
        self.assertLess(clock.longest_sleep, 2.0)

    def test_a_hostile_header_cannot_park_us_indefinitely(self):
        self.config.rate_limit_first_n = 1
        self.config.retry_after_header = "86400"
        clock = FakeClock()
        client = self.fake_client(clock)

        client.status()
        self.assertLessEqual(clock.longest_sleep, erp_client.MAX_RETRY_AFTER_SECONDS + 0.01)

    def test_a_garbage_header_does_not_break_the_retry(self):
        self.config.rate_limit_first_n = 2
        self.config.retry_after_header = "whenever you feel like it"
        clock = FakeClock()
        client = self.fake_client(clock)

        self.assertEqual(client.status()["entry_count"], 45)
        self.assertGreaterEqual(clock.longest_sleep, 1.1)

    def test_a_throttled_login_also_honours_the_header(self):
        """The rate limiter sits in front of routing, so POST /erp/login can
        be throttled too. That branch has its own cooldown call."""
        self.config.rate_limit_first_n = 1
        self.config.retry_after_header = "9"
        clock = FakeClock()
        client = self.fake_client(clock)

        client.ensure_session()
        self.assertEqual(client.metrics.logins, 1)
        self.assertEqual(client.metrics.retries_rate_limited, 1)
        self.assertGreaterEqual(clock.longest_sleep, 9.0)


class TestSessionExpiry(StubServerTestCase):
    """The two expiry conditions the ERP enforces, finally tested directly.

    Before this, both were covered only indirectly: reproducing them for
    real needs 250 requests or a thirteen-minute wait. Making the limits and
    the clock injectable turns both into sub-second tests.
    """

    def fake_client(self, clock, **kwargs):
        kwargs.setdefault("requests_per_second", 500.0)
        kwargs.setdefault("backoff_base_seconds", 0.01)
        kwargs.setdefault("backoff_cap_seconds", 0.05)
        kwargs.setdefault("time_budget_seconds", 100_000.0)
        return ErpClient(base_url=self.base_url, clock=clock, sleeper=clock.sleep, **kwargs)

    # -- by number of uses -------------------------------------------------

    def test_session_is_renewed_before_the_use_limit_is_reached(self):
        """10 pages with a 3-use budget: login, 3 pages, login, 3 pages,
        login, 3 pages, login, 1 page. Four logins, no SES-401 anywhere."""
        self.config.total_entries = 200          # 10 pages
        clock = FakeClock()
        client = self.fake_client(clock, session_max_uses=3)

        snapshot = client.snapshot()

        self.assertTrue(snapshot.complete)
        self.assertEqual(len(snapshot.entries), 200)
        self.assertEqual(client.metrics.logins, 4)
        # Renewal is proactive, so the server never had to reject us.
        self.assertEqual(client.metrics.retries_session_expired, 0)

    def test_one_login_is_enough_when_the_budget_is_generous(self):
        """The control case. Same dump, default limits, a single login."""
        self.config.total_entries = 200
        clock = FakeClock()
        client = self.fake_client(clock)

        client.snapshot()
        self.assertEqual(client.metrics.logins, 1)

    def test_the_use_counter_ignores_anonymous_calls(self):
        """/erp/estado is anonymous, so it must not burn a session use."""
        clock = FakeClock()
        client = self.fake_client(clock, session_max_uses=2)

        client.ensure_session()
        for _ in range(5):
            client.status()

        self.assertEqual(client.metrics.logins, 1)
        self.assertEqual(client._session_uses, 0)

    def test_an_ora00600_still_consumes_a_use(self):
        """The fault is injected after session validation, so the server has
        already charged us for the request. Counting it is what keeps our
        renewal ahead of the server's."""
        clock = FakeClock()
        client = self.fake_client(clock, session_max_uses=100)
        self.config.fail_first_n_authenticated = 1

        client.page(1)

        self.assertEqual(client.metrics.retries_ora00600, 1)
        self.assertEqual(client._session_uses, 2)   # the failed one and the good one

    def test_a_ses401_does_not_consume_a_use(self):
        """The server returns before incrementing its counter, so we must
        not increment ours either, or we would renew too early forever."""
        clock = FakeClock()
        client = self.fake_client(clock)
        self.config.expire_session_after = 1

        client.page(1)

        self.assertEqual(client.metrics.retries_session_expired, 1)
        self.assertEqual(client.metrics.logins, 2)
        self.assertEqual(client._session_uses, 1)   # only the successful retry

    # -- by age ------------------------------------------------------------

    def test_session_is_renewed_once_it_gets_old(self):
        """The 13-minute case, in about a millisecond."""
        clock = FakeClock()
        client = self.fake_client(clock, session_max_age_seconds=780.0)

        client.page(1)
        self.assertEqual(client.metrics.logins, 1)

        clock.advance(781.0)                      # the session is now stale
        client.page(2)

        self.assertEqual(client.metrics.logins, 2)
        self.assertEqual(client.metrics.retries_session_expired, 0)

    def test_a_young_session_is_reused(self):
        """Guards the test above: without this, a client that re-logged in on
        every single call would also pass it."""
        clock = FakeClock()
        client = self.fake_client(clock, session_max_age_seconds=780.0)

        client.page(1)
        clock.advance(100.0)
        client.page(2)
        clock.advance(100.0)
        client.page(3)

        self.assertEqual(client.metrics.logins, 1)

    def test_expiry_is_evaluated_at_the_boundary_not_after_it(self):
        """Exactly at the limit we renew. The server's own check is `>=`
        too, and being one request late costs a wasted round trip."""
        clock = FakeClock()
        client = self.fake_client(clock, session_max_age_seconds=600.0)

        client.page(1)
        self.assertFalse(client.session_expired)
        clock.advance(600.0)
        self.assertTrue(client.session_expired)

    def test_the_clock_resets_on_renewal(self):
        clock = FakeClock()
        client = self.fake_client(clock, session_max_age_seconds=500.0)

        client.page(1)
        clock.advance(501.0)
        client.page(2)                            # renews here
        self.assertEqual(client.metrics.logins, 2)

        clock.advance(499.0)                      # still inside the new window
        client.page(3)
        self.assertEqual(client.metrics.logins, 2)

    def test_both_limits_are_rejected_when_nonsensical(self):
        for kwargs in ({"session_max_uses": 0}, {"session_max_uses": -1},
                       {"session_max_age_seconds": 0}, {"session_max_age_seconds": -5}):
            with self.subTest(**kwargs):
                with self.assertRaises(ValueError):
                    ErpClient(**kwargs)

    def test_defaults_stay_below_what_the_server_enforces(self):
        """The whole point of renewing early. The server cuts us off at 300
        uses / 900 s; if these defaults ever drift above that, every long
        dump starts paying for SES-401 round trips."""
        self.assertLess(erp_client.DEFAULT_SESSION_MAX_USES, 300)
        self.assertLess(erp_client.DEFAULT_SESSION_MAX_AGE_SECONDS, 900.0)


class TestFakeClockIsHonest(StubServerTestCase):
    """If the fake clock were not actually wired in, every test above would
    pass vacuously. These two check that it really drives the client."""

    def test_the_client_reads_the_injected_clock(self):
        clock = FakeClock(start=777.0)
        client = ErpClient(base_url=self.base_url, clock=clock, sleeper=clock.sleep,
                           requests_per_second=500.0)
        self.assertEqual(client._session_started, 777.0)
        self.assertEqual(client._deadline(), 777.0 + client.time_budget_seconds)

    def test_sleeping_is_recorded_rather_than_endured(self):
        self.config.rate_limit_first_n = 1
        self.config.retry_after_header = "25"
        clock = FakeClock()
        client = ErpClient(base_url=self.base_url, clock=clock, sleeper=clock.sleep,
                           requests_per_second=500.0, time_budget_seconds=100_000.0)

        wall_clock_before = time.monotonic()
        client.status()
        wall_clock_spent = time.monotonic() - wall_clock_before

        self.assertGreaterEqual(clock.longest_sleep, 25.0)   # the client thinks it waited
        self.assertLess(wall_clock_spent, 5.0)               # nobody actually did



if __name__ == "__main__":
    unittest.main(verbosity=2)
