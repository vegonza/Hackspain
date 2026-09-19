def order_key(value: str) -> str:
    """Preserve internal whitespace, punctuation and leading zeroes."""
    return value.strip().upper()


def compact_identifier(value: str) -> str:
    """Normalize NIF and IBAN without guessing OCR character substitutions."""
    return ''.join(value.split()).upper()
