import csv
from io import StringIO

from accounting.models import AccountingReport


def accounting_csv(report: AccountingReport) -> bytes:
    output = StringIO()
    writer = csv.writer(output, delimiter=";", lineterminator="\n")
    writer.writerow([
        "Documento", "Número de factura", "Fecha", "Proveedor", "NIF", "Categoría",
        "Cuenta propuesta", "Base imponible", "Tipo IVA", "IVA soportado", "Total",
        "Gasto potencialmente deducible", "IVA potencialmente deducible", "Estado", "Motivos de revisión",
    ])
    for invoice in report.invoices:
        writer.writerow([
            invoice.document_name,
            invoice.invoice_number or "",
            invoice.invoice_date.isoformat() if invoice.invoice_date is not None else "",
            invoice.supplier_name or "",
            invoice.supplier_nif or "",
            invoice.category,
            invoice.account_code,
            invoice.tax_base if invoice.tax_base is not None else "",
            invoice.vat_rate if invoice.vat_rate is not None else "",
            invoice.vat_amount if invoice.vat_amount is not None else "",
            invoice.total if invoice.total is not None else "",
            invoice.potential_deductible_expense,
            invoice.potential_deductible_vat,
            invoice.status,
            ",".join(invoice.review_reasons),
        ])
    return ("\ufeff" + output.getvalue()).encode("utf-8")
