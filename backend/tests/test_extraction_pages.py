import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.extraction_3.pages import render_pages


class ExtractionPageTests(unittest.TestCase):
    def test_returns_all_pages_in_numeric_order_and_cleans_temporary_files(self) -> None:
        def render(arguments: list[str], *, input: bytes, capture_output: bool, check: bool) -> None:
            self.assertEqual(input, b"PDF")
            self.assertTrue(capture_output)
            self.assertTrue(check)
            self.directory = Path(arguments[-1]).parent
            for number in (10, 2, 1):
                (self.directory / f"page-{number}.jpg").write_bytes(f"image {number}".encode())

        with patch("pipeline.extraction_3.pages.subprocess.run", side_effect=render):
            pages = render_pages(b"PDF")
        self.assertEqual(pages, [b"image 1", b"image 2", b"image 10"])
        self.assertFalse(self.directory.exists())

    def test_render_errors_are_propagated(self) -> None:
        with patch("pipeline.extraction_3.pages.subprocess.run", side_effect=subprocess.CalledProcessError(1, "pdftoppm")):
            with self.assertRaises(subprocess.CalledProcessError):
                render_pages(b"invalid PDF")

    def test_missing_rendered_pages_fail_instead_of_sending_text_only(self) -> None:
        with patch("pipeline.extraction_3.pages.subprocess.run"):
            with self.assertRaisesRegex(ValueError, "no pages"):
                render_pages(b"PDF")
