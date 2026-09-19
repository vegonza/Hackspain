import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import HTTPException

from shared.logger import get_logger

OFFICE_EXTENSIONS = {'.doc', '.docx', '.odt', '.rtf', '.ppt', '.pptx', '.odp', '.xls', '.xlsx', '.ods'}
SUPPORTED_EXTENSIONS = OFFICE_EXTENSIONS | {'.pdf'}
logger = get_logger()


def to_pdf(content: bytes, name: str) -> bytes:
    """Convert Office uploads with an isolated LibreOffice profile for each request."""
    extension = Path(name).suffix.lower()
    if extension == '.pdf':
        if not content.startswith(b'%PDF-'):
            raise HTTPException(status_code=400, detail='invalid_pdf')
        return content
    if extension not in OFFICE_EXTENSIONS:
        raise HTTPException(status_code=400, detail='unsupported_file_type')
    logger.info('[CONVERSION] Converting %s to PDF', name)
    with TemporaryDirectory(prefix='invoice-conversion-') as directory:
        root = Path(directory)
        source = root / f'source{extension}'
        source.write_bytes(content)
        try:
            subprocess.run([
                'libreoffice', f'-env:UserInstallation={(root / "profile").as_uri()}',
                '--headless', '--norestore', '--convert-to', 'pdf', '--outdir', str(root), str(source),
            ], check=True, capture_output=True, timeout=120)
            converted = (root / 'source.pdf').read_bytes()
            if not converted.startswith(b'%PDF-'):
                raise ValueError('Conversion did not produce a PDF')
        except (subprocess.SubprocessError, OSError, ValueError) as error:
            logger.warning('[CONVERSION] Could not convert %s: %s', name, type(error).__name__)
            raise HTTPException(status_code=422, detail='conversion_failed') from error
    logger.info('[CONVERSION] Converted %s to PDF (%s bytes)', name, len(converted))
    return converted
