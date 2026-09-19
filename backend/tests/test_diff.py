import unittest

from pipeline.diff import markdown_diff


class MarkdownDiffTests(unittest.TestCase):
    def test_accent_change_highlights_only_the_changed_character(self) -> None:
        before = "Documento generado por el sistema de facturación del proveedor."
        after = "Documento generado por el sistema de facturacion del proveedor."
        removed, added = markdown_diff(before, after)
        self.assertEqual([span.text for span in removed.spans if span.changed], ["ó"])
        self.assertEqual([span.text for span in added.spans if span.changed], ["o"])
        self.assertEqual((removed.before, removed.after), (1, None))
        self.assertEqual((added.before, added.after), (None, 1))

    def test_character_insertions_deletions_and_multiple_edits(self) -> None:
        for before, after, removed_text, added_text in (
            ("Total 100 €", "Total -100 €", "", "-"),
            ("Total -100 €", "Total 100 €", "-", ""),
            ("Base 100; IVA 21", "Base 300; IVA 45", "121", "345"),
        ):
            with self.subTest(before=before, after=after):
                removed, added = markdown_diff(before, after)
                self.assertEqual("".join(span.text for span in removed.spans if span.changed), removed_text)
                self.assertEqual("".join(span.text for span in added.spans if span.changed), added_text)

    def test_inserted_line_does_not_shift_highlights_for_following_replacements(self) -> None:
        lines = markdown_diff("Nombre: José\nTotal: 100", "Nombre: Jose\nNota adicional\nTotal: 200")
        self.assertEqual([(line.kind, line.before, line.after) for line in lines], [
            ("removed", 1, None), ("removed", 2, None),
            ("added", None, 1), ("added", None, 2), ("added", None, 3),
        ])
        self.assertEqual("".join(span.text for span in lines[-1].spans if span.changed), "2")
        for line in lines:
            self.assertEqual("".join(span.text for span in line.spans), line.text)

    def test_full_line_changes_blank_lines_and_markdown_preserve_source(self) -> None:
        for before, after in (
            ("", "Nueva línea"), ("Línea eliminada", ""),
            ("Inicio\n\nFin", "Inicio\nFin"),
            ("**A**\n\nTotal: 100", "**B**\nNota\nTotal: 200"),
            ("Igual\n<texto>", "Igual\n<texto>"),
        ):
            with self.subTest(before=before, after=after):
                lines = markdown_diff(before, after)
                self.assertEqual([line.text for line in lines if line.kind != "added"], before.splitlines())
                self.assertEqual([line.text for line in lines if line.kind != "removed"], after.splitlines())
                for line in lines:
                    self.assertEqual("".join(span.text for span in line.spans), line.text)
                    if line.kind == "equal":
                        self.assertFalse(any(span.changed for span in line.spans))
