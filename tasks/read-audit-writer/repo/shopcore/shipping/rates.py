"""Shipping rate tables."""

ZONES = {"domestic": 500, "near": 1200, "far": 2500}
FREE_OVER_CENTS = 7500


def quote(zone: str, subtotal_cents: int) -> int:
    if subtotal_cents >= FREE_OVER_CENTS:
        return 0
    return ZONES[zone]
