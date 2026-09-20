from extractor.recovery import IdentifierTrace
from extractor.verifactu import VerifactuQR


class ExtractionMetadata(IdentifierTrace):
    verifactu: VerifactuQR | None = None
