from decimal import Decimal


def to_float(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def round1(value: float) -> float:
    return round(float(value), 1)
