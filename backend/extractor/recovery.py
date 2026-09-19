from typing import Literal

from pydantic import BaseModel

from extractor.extraction import InvoiceExtraction
from shared.identifiers import compact_identifier, normalize_tax_id
from suppliers.models import Supplier


class IdentifierCorrection(BaseModel):
    field: Literal['supplier_nif', 'iban']
    original: str
    corrected: str
    supplier_id: str
    matched_field: Literal['supplier_nif', 'iban']
    matched_value: str


def one_character_apart(original: str, candidate: str) -> bool:
    """Accept one substitution, never insertions, deletions or missing identifiers."""
    return len(original) == len(candidate) and sum(a != b for a, b in zip(original, candidate)) == 1


def recover_identifiers(
    invoice: InvoiceExtraction, suppliers: list[Supplier],
) -> tuple[InvoiceExtraction, list[IdentifierCorrection]]:
    """Infer at most one correction from an exact, unique master-data match."""
    nif = normalize_tax_id(invoice.supplier_nif)
    iban = compact_identifier(invoice.iban)
    nif_matches = [supplier for supplier in suppliers if nif and supplier.tax_id == nif]
    iban_matches = [supplier for supplier in suppliers if iban and supplier.iban == iban]
    correction: IdentifierCorrection | None = None
    if len(nif_matches) == 1 and one_character_apart(iban, nif_matches[0].iban):
        supplier = nif_matches[0]
        correction = IdentifierCorrection(
            field='iban', original=invoice.iban, corrected=supplier.iban,
            supplier_id=supplier.supplier_id, matched_field='supplier_nif', matched_value=nif,
        )
    elif len(iban_matches) == 1 and one_character_apart(nif, iban_matches[0].tax_id):
        supplier = iban_matches[0]
        correction = IdentifierCorrection(
            field='supplier_nif', original=invoice.supplier_nif, corrected=supplier.tax_id,
            supplier_id=supplier.supplier_id, matched_field='iban', matched_value=iban,
        )
    if correction is None:
        return invoice, []
    return invoice.model_copy(update={correction.field: correction.corrected}), [correction]
