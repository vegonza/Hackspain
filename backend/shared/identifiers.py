def order_key(value: str) -> str:
    """Preserve internal whitespace, punctuation and leading zeroes."""
    return value.strip().upper()


def compact_identifier(value: str) -> str:
    """Normalize identifiers without guessing OCR character substitutions."""
    return ''.join(value.split()).upper()


def normalize_tax_id(value: str) -> str:
    """Ignore fiscal ID formatting while preserving letters and leading zeroes."""
    return compact_identifier(value).translate(str.maketrans('', '', './-'))
