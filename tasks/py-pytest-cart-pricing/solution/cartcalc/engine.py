"""Order pricing engine. See SPEC.md for the rules."""

from decimal import ROUND_HALF_UP, Decimal

from cartcalc.codes import FIXED, PERCENT
from cartcalc.model import Line
from cartcalc.tax import EXEMPT_CATEGORIES, RATES

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def line_subtotal(line: Line) -> Decimal:
    price = line.unit_price
    if line.qty >= 50:
        price = price * Decimal("0.90")
    elif line.qty >= 10:
        price = price * Decimal("0.95")
    return money(price * line.qty)


def apply_codes(subtotal: Decimal, codes: list[str]) -> Decimal:
    for code in codes:
        if code not in PERCENT and code not in FIXED:
            raise ValueError(f"unknown discount code {code!r}")
    amount = subtotal
    for code in (c for c in codes if c in PERCENT):
        amount = money(amount * (1 - PERCENT[code] / 100))
    for code in (c for c in codes if c in FIXED):
        amount = amount - FIXED[code]
    return max(money(amount), ZERO)


def is_exempt(category: str) -> bool:
    return category.strip().lower() in EXEMPT_CATEGORIES


def price_order(lines: list[Line], codes: list[str], region: str) -> dict[str, Decimal]:
    if region not in RATES:
        raise ValueError(f"unknown region {region!r}")
    subtotals = [line_subtotal(line) for line in lines]
    subtotal = money(sum(subtotals, ZERO))
    discounted = apply_codes(subtotal, codes)
    taxable = sum((s for s, line in zip(subtotals, lines) if not is_exempt(line.category)), ZERO)
    if subtotal == 0:
        tax = ZERO
    else:
        tax = money(discounted * (taxable / subtotal) * RATES[region])
    return {"subtotal": subtotal, "discounted": discounted, "tax": tax,
            "total": discounted + tax}
