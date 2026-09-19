from difflib import SequenceMatcher
from typing import Literal

from pydantic import BaseModel

# Preview data for one uploaded document; never written to storage.
PREVIEW_DOCUMENT_ID = "8a457631-8525-452f-aab6-cf668c63c948"
EXTRACTED_TEXT = """Ofimática Cieza S.L.
Murcia · NIF B30455812
Cuenta de abono (IBAN): ES60 0182 5322 1802 0158 8391
Nº de factura: F26-9524
Fecha de emisión: 15/01/2026
Su pedido: PO-2026-0070
Facturar a: Banco Miralmar S.A. — CIF A58231074
Paseo de la Castellana 214, Madrid
Concepto                         Cantidad    Importe
Transporte urgente              1           458,04 €
Horas de soporte                1         5.169,36 €
Consumibles                     1           916,09 €
Importe base: 6.543,49 €
Cuota IVA (21%): 1.374,13 €
Total factura: 7.917,62 €
Documento generado por el sistema de facturación del proveedor."""

MERGED_MARKDOWN = """# **Ofimática Cieza S.L.**

Murcia · NIF B30455812

Cuenta de abono (IBAN): ES60 0182 5322 1802 0158 8391

## **Nº de factura: F26-9524**

Fecha de emisión: 15/01/2026

Su pedido: PO-2026-0070

Facturar a: Banco Miralmar S.A. — CIF A58231074

Paseo de la Castellana 214, Madrid

| Concepto | Cantidad | Importe |
| --- | ---: | ---: |
| Transporte urgente | 1 | 458,04 € |
| Horas de soporte | 1 | 5.169,36 € |
| Consumibles | 1 | 916,09 € |

Importe base: 6.543,49 €

Cuota IVA (21%): 1.374,13 €

**Total factura: 7.917,62 €**

Documento generado por el sistema de facturación del proveedor."""


class DiffLine(BaseModel):
    kind: Literal["equal", "removed", "added"]
    text: str
    before: int | None
    after: int | None


def markdown_diff(before: str, after: str) -> list[DiffLine]:
    """Compare Markdown source lines, preserving both line number sequences."""
    original, merged = before.splitlines(), after.splitlines()
    lines: list[DiffLine] = []
    for operation, start, end, new_start, new_end in SequenceMatcher(None, original, merged, autojunk=False).get_opcodes():
        if operation == "equal":
            lines.extend(DiffLine(kind="equal", text=original[i], before=i + 1, after=new_start + i - start + 1) for i in range(start, end))
        else:
            lines.extend(DiffLine(kind="removed", text=original[i], before=i + 1, after=None) for i in range(start, end))
            lines.extend(DiffLine(kind="added", text=merged[i], before=None, after=i + 1) for i in range(new_start, new_end))
    return lines
