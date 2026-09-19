from decimal import Decimal, ROUND_HALF_UP

# Fixed reconciliation rates inferred from the challenge data, not dated market quotes.
RECONCILIATION_RATES: dict[str, Decimal] = {
    'EUR': Decimal('1'),
    'USD': Decimal('0.92'),
    'GBP': Decimal('1.17'),
    'CHF': Decimal('1.05'),
    'JPY': Decimal('0.00617'),
    'BRL': Decimal('1') / Decimal('6.2'),
    'MXN': Decimal('0.05'),
}


def reconciliation_rate(currency: str) -> Decimal | None:
    return RECONCILIATION_RATES.get(currency)


def to_euros(amount: Decimal, rate: Decimal) -> Decimal:
    return (amount * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
