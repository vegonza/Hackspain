import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from documents.batch import refresh_order_index
from pipeline.extraction_4.extraction import InvoiceExtraction


class BatchTests(unittest.TestCase):
    def test_changed_extraction_removes_stale_order_and_deleted_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "pdfs"
            source.mkdir()
            extracted = root / "extracted"
            document = extracted / "scan"
            document.mkdir(parents=True)
            (source / "scan.pdf").write_bytes(b"PDF fixture")
            extraction = InvoiceExtraction(
                invoice_number="I-1", supplier_name="Vendor", supplier_nif="N-1", iban="Account",
                invoice_date="2026-01-01", purchase_order="PO-2026-0010", line_items=[],
                tax_base="10", vat_rate="21", vat_amount="2.10", total="12.10", notes=[], uncertainties=[],
            )
            (document / "features.json").write_text(extraction.model_dump_json())
            with patch("documents.batch.extract_text", return_value="") as read:
                first = refresh_order_index(source, root / "index.json", extracted)
                self.assertEqual(first.other_documents("PO-2026-0010", "other.pdf"), ["scan.pdf"])
                refresh_order_index(source, root / "index.json", extracted)
                self.assertEqual(read.call_count, 1)
                extraction.purchase_order = "PO-2026-0020"
                (document / "features.json").write_text(extraction.model_dump_json())
                changed = refresh_order_index(source, root / "index.json", extracted)
                self.assertEqual(changed.other_documents("PO-2026-0010", "other.pdf"), [])
                self.assertEqual(changed.other_documents("PO-2026-0020", "other.pdf"), ["scan.pdf"])
                self.assertEqual(read.call_count, 2)
                (source / "scan.pdf").unlink()
                deleted = refresh_order_index(source, root / "index.json", extracted)
                self.assertEqual(deleted.documents, {})


if __name__ == "__main__":
    unittest.main()
