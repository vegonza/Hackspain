import re
from collections.abc import Sequence
from datetime import datetime
from io import BytesIO
from typing import Literal
from urllib.parse import parse_qs, urlsplit

from PIL import Image
from pydantic import BaseModel
from zxingcpp import BarcodeFormat, read_barcodes


class VerifactuQR(BaseModel):
    url: str
    page: int
    environment: Literal['production', 'test']


def parse_verifactu(value: str, page: int) -> VerifactuQR | None:
    """Recognize AEAT invoice verification links without requesting their contents."""
    try:
        url = urlsplit(value)
        environments: dict[str, Literal['production', 'test']] = {
            'www2.agenciatributaria.gob.es': 'production', 'prewww2.aeat.es': 'test',
        }
        if (url.scheme != 'https' or url.netloc not in environments
                or url.path != '/wlpl/TIKE-CONT/ValidarQR' or url.fragment):
            return None
        parameters = parse_qs(url.query, strict_parsing=True, keep_blank_values=True)
        if set(parameters) != {'nif', 'numserie', 'fecha', 'importe'}:
            return None
        if any(len(values) != 1 or not values[0] for values in parameters.values()):
            return None
        nif, number, date, amount = (parameters[key][0] for key in ('nif', 'numserie', 'fecha', 'importe'))
        if not re.fullmatch(r'[A-Z0-9]{9}', nif) or not re.fullmatch(r'[\x20-\x7e]{1,60}', number):
            return None
        if not re.fullmatch(r'\d{2}-\d{2}-\d{4}', date) or not re.fullmatch(r'-?\d{1,12}(?:\.\d{1,2})?', amount):
            return None
        datetime.strptime(date, '%d-%m-%Y')
        return VerifactuQR(url=value, page=page, environment=environments[url.netloc])
    except ValueError:
        return None


def detect_verifactu(pages: Sequence[bytes]) -> VerifactuQR | None:
    matches: dict[str, VerifactuQR] = {}
    for number, content in enumerate(pages, start=1):
        with Image.open(BytesIO(content)) as image:
            codes = read_barcodes(image.convert('RGB'), formats=BarcodeFormat.QRCode)
        for code in codes:
            result = parse_verifactu(code.text, number)
            if result is not None and result.url not in matches:
                matches[result.url] = result
    return next(iter(matches.values())) if len(matches) == 1 else None
