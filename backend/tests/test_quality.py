import json
import unittest
from unittest.mock import patch

from pipeline.merge_3.quality import (
    Correction, OCRCorrections, apply_corrections, merge_text, tokens,
)


class CorrectionTests(unittest.TestCase):
    def test_control_characters_in_model_corrections_are_rejected(self) -> None:
        for character in ("\x00", "\x86", "\x94"):
            result = OCRCorrections(corrections=[Correction(
                original="Nº", replacement=f"N{character}", reason="Model punctuation change",
            )], unresolved=[])
            with self.assertRaisesRegex(ValueError, "control characters"):
                apply_corrections("Factura Nº", result)

    def test_repeated_model_proposal_is_applied_once(self) -> None:
        edit = Correction(original="Miramar", replacement="Miralmar", reason="Visible spelling")
        result = OCRCorrections(corrections=[edit, edit], unresolved=[])
        self.assertEqual(apply_corrections("Banco Miramar", result), "Banco Miralmar")
        self.assertEqual(len(result.corrections), 1)

    def test_edits_refer_to_original_not_previous_replacements(self) -> None:
        result = OCRCorrections(corrections=[
            Correction(original="A", replacement="B", reason="First character"),
            Correction(original="B", replacement="C", reason="Second character"),
        ], unresolved=[])
        self.assertEqual(apply_corrections("A B", result), "B C")

    def test_ambiguous_or_overlapping_edits_are_rejected(self) -> None:
        result = OCRCorrections(corrections=[
            Correction(original="ABC", replacement="DEF", reason="Full span"),
            Correction(original="BC", replacement="GH", reason="Overlapping span"),
        ], unresolved=[])
        with self.assertRaises(ValueError):
            apply_corrections("ABC", result)
        result.corrections = [Correction(original="A", replacement="B", reason="Ambiguous")]
        with self.assertRaises(ValueError):
            apply_corrections("A A", result)

    def test_merge_sends_both_sources_in_one_text_only_call(self) -> None:
        native = "Banco Miralmar\nNota {instrucciones}"
        with patch("pipeline.merge_3.quality.create_extractor") as factory:
            extract = factory.return_value.__enter__.return_value.run
            extract.return_value = OCRCorrections(corrections=[Correction(
                original="Miramar", replacement="Miralmar", reason="Native text spelling",
            )], unresolved=["Nota no coincidente"])
            corrected, corrections = merge_text(native, "Banco Miramar")
        self.assertEqual(corrected, "Banco Miralmar")
        self.assertEqual(corrections.unresolved, ["Nota no coincidente"])
        extract.assert_called_once()
        self.assertEqual(json.loads(extract.call_args.args[1]), {
            "native_text": native, "ocr_markdown": "Banco Miramar",
        })
        self.assertEqual(extract.call_args.args[2], OCRCorrections)
        self.assertEqual(extract.call_args.kwargs, {"usage": None})

    def test_no_changes_preserves_ocr_content_exactly(self) -> None:
        markdown = "# Factura\n| Servicio | 10,00 |\nSello: Recibido"
        with patch("pipeline.merge_3.quality.create_extractor") as factory:
            extract = factory.return_value.__enter__.return_value.run
            extract.return_value = OCRCorrections(corrections=[], unresolved=[])
            merged, _ = merge_text("", markdown)
        self.assertEqual(merged, markdown)
        extract.assert_called_once()

    def test_comparison_keeps_financial_signs_but_ignores_markdown(self) -> None:
        self.assertNotEqual(tokens("TOTAL -100,00"), tokens("TOTAL 100,00"))
        self.assertEqual(tokens("**facturación**"), tokens("facturacion"))


if __name__ == "__main__":
    unittest.main()
