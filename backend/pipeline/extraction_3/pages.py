import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from shared.logger import get_logger

logger = get_logger()


def render_pages(pdf: bytes) -> list[bytes]:
    """Render every PDF page as a JPEG, in document order, for invoice extraction."""
    with TemporaryDirectory() as directory:
        prefix = Path(directory) / "page"
        subprocess.run(
            ["pdftoppm", "-jpeg", "-r", "150", "-scale-to", "2000", "-jpegopt", "quality=90", "-", str(prefix)],
            input=pdf, capture_output=True, check=True,
        )
        paths = sorted(Path(directory).glob("page-*.jpg"), key=lambda path: int(path.stem.rsplit("-", 1)[1]))
        if not paths:
            raise ValueError("PDF rendering returned no pages")
        images = [path.read_bytes() for path in paths]
    logger.info("[EXTRACTION] Rendered %s invoice pages", len(images))
    return images
