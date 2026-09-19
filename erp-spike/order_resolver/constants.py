#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import re

#: The bank receiving every invoice. Its tax id appears on all documents and
#: must never be mistaken for the supplier's.
CLIENT_TAX_ID: str = "A58231074"

#: The only shape a purchase order takes in this dataset. Verified against all
#: 516 ERP entries and all 471 invoices that carry a text layer.
ORDER_CODE: re.Pattern[str] = re.compile(r"\bPO-(\d{4})-(\d{4})\b")

#: Deliberately permissive: catches separators and digit/letter confusions that
#: OCR introduces. Only used to *propose* a repair, never as a direct match.
ORDER_CODE_LOOSE: re.Pattern[str] = re.compile(
    r"\bP[O0Q]\s*[-–—_. ]?\s*([0-9OQlIiSsBbZz]{4})\s*[-–—_. ]?\s*([0-9OQlIiSsBbZz]{1,4})\b"
)

#: Characters OCR habitually swaps for digits.
GLYPH_TO_DIGIT: dict[int, str] = str.maketrans({
    "O": "0", "o": "0", "Q": "0", "D": "0",
    "l": "1", "I": "1", "i": "1", "|": "1",
    "S": "5", "s": "5",
    "B": "8",
    "Z": "2", "z": "2",
    "G": "6",
    "T": "7",
})

SPANISH_MONTHS: dict[str, int] = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}

TAX_ID: re.Pattern[str] = re.compile(r"\b([A-HJ-NP-SUVW]\d{8}|\d{8}[A-Z]|[XYZ]\d{7}[A-Z])\b")

AMOUNT_ES_GROUPED: re.Pattern[str] = re.compile(r"^\d{1,3}(\.\d{3})+,\d{1,2}$")
AMOUNT_ES_PLAIN: re.Pattern[str] = re.compile(r"^\d+,\d{1,2}$")
AMOUNT_EN_GROUPED: re.Pattern[str] = re.compile(r"^\d{1,3}(,\d{3})+\.\d{1,2}$")
AMOUNT_EN_PLAIN: re.Pattern[str] = re.compile(r"^\d+(\.\d{1,2})?$")
AMOUNT_INTEGER: re.Pattern[str] = re.compile(r"^\d+$")

DATE_NUMERIC: re.Pattern[str] = re.compile(r"\b(\d{1,2})\s*[/.\-]\s*(\d{1,2})\s*[/.\-]\s*(\d{4})\b")
DATE_ISO: re.Pattern[str] = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
DATE_WORDS: re.Pattern[str] = re.compile(
    r"\b(\d{1,2})\s+de\s+([A-Za-zÁ-Úá-ú]+)\s+de\s+(\d{4})\b", re.IGNORECASE
)
