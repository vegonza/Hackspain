import re
from datetime import date, datetime
from decimal import Decimal
from xml.etree import ElementTree

from erp.models import ErpEntry
from erp.warnings import ErpWarning

MIN_ERP_DATE = date(1900, 1, 1)


def parse_date(raw: str) -> tuple[date | None, ErpWarning | None]:
    text = raw.strip()
    if not text:
        return None, ErpWarning.MISSING_DATE
    for pattern, format_string, warning in (
        (r"[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}", "%d/%m/%Y", None),
        (r"[0-9]{4}-[0-9]{2}-[0-9]{2}", "%Y-%m-%d", ErpWarning.ISO_DATE_FORMAT),
    ):
        if re.fullmatch(pattern, text):
            try:
                return datetime.strptime(text, format_string).date(), warning
            except ValueError:
                return None, ErpWarning.INVALID_DATE
    return None, ErpWarning.INVALID_DATE


def parse_amount(raw: str) -> tuple[Decimal | None, ErpWarning | None]:
    """Prefer the documented Spanish format; flag unambiguous English amounts."""
    text = raw.strip()
    if not text:
        return None, ErpWarning.MISSING_AMOUNT
    if re.fullmatch(r"[+-]?(?:[0-9]+|[0-9]{1,3}(?:\.[0-9]{3})+)(?:,[0-9]+)?", text):
        return Decimal(text.replace(".", "").replace(",", ".")), None
    if re.fullmatch(r"[+-]?[0-9]{1,3}(?:[ \u00a0\u202f][0-9]{3})+(?:,[0-9]+)?", text):
        return Decimal(text.translate(str.maketrans({" ": "", "\u00a0": "", "\u202f": "", ",": "."}))), None
    if re.fullmatch(r"[+-]?(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.[0-9]+)?", text):
        return Decimal(text.replace(",", "")), ErpWarning.ENGLISH_AMOUNT_FORMAT
    return None, ErpWarning.INVALID_AMOUNT


def parse_entry(element: ElementTree.Element) -> ErpEntry:
    """Parse one asiento; malformed data produces warnings, malformed structure fails."""
    if element.tag != "asiento":
        raise ValueError("Expected an asiento XML element")
    fields = {
        "entry_id": "id", "supplier_id": "proveedor", "tax_id": "nif",
        "order_id": "pedido", "status": "estado", "raw_date": "fecha", "raw_amount": "importe",
    }
    values = {field: element.findtext(tag, default="") for field, tag in fields.items()}
    parsed_date, date_warning = parse_date(values["raw_date"])
    amount, amount_warning = parse_amount(values["raw_amount"])
    warnings = [warning for warning in (date_warning, amount_warning) if warning is not None]
    if parsed_date is not None and not MIN_ERP_DATE <= parsed_date <= date.today():
        warnings.append(ErpWarning.DATE_OUT_OF_RANGE)
    for field in ("entry_id", "supplier_id", "tax_id", "order_id", "status"):
        values[field] = values[field].strip()
        if not values[field]:
            warnings.append(ErpWarning(f"missing_{field}"))
    if values["status"] and values["status"] not in ("PENDIENTE", "PAGADA"):
        warnings.append(ErpWarning.UNKNOWN_STATUS)
    if any("?" in values[field] for field in ("entry_id", "supplier_id", "tax_id", "order_id")):
        warnings.append(ErpWarning.POSSIBLE_CHARACTER_LOSS)
    return ErpEntry(**values, date=parsed_date, amount=amount, warnings=warnings)


def parse_entry_xml(payload: bytes) -> ErpEntry:
    """Parse bytes so the XML declaration controls character decoding."""
    return parse_entry(ElementTree.fromstring(payload))
