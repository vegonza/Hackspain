from xml.etree import ElementTree

from pydantic import ValidationError

from erp.errors import ErpProtocolError
from erp.models import ErpPage
from erp.parsing import parse_entry


def parse_page(root: ElementTree.Element) -> ErpPage:
    """Keep the ERP's pagination metadata and every entry, including duplicates."""
    meta = root.find("meta")
    entries = root.find("asientos")
    if root.tag != "respuesta" or meta is None or entries is None:
        raise ErpProtocolError("ERP page has no metadata or entries container")
    fields = {
        "number": "pagina", "total_pages": "paginas",
        "total_entries": "total", "page_size": "por_pagina",
    }
    values: dict[str, int] = {}
    for field, tag in fields.items():
        text = meta.findtext(tag)
        if text is None:
            raise ErpProtocolError(f"ERP page metadata is missing {tag}")
        try:
            values[field] = int(text)
        except ValueError as exc:
            raise ErpProtocolError(f"ERP page metadata has invalid {tag}") from exc
    try:
        page = ErpPage(**values, entries=[parse_entry(entry) for entry in entries.findall("asiento")])
    except ValidationError as exc:
        raise ErpProtocolError("ERP page metadata is out of range") from exc
    if page.number > page.total_pages:
        raise ErpProtocolError("ERP page number exceeds its total pages")
    return page
