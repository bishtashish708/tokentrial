"""Tiny ledger utilities for parsing accounting-style amounts."""

from decimal import Decimal, InvalidOperation


def parse_amount(text: str) -> Decimal:
    """Parse amounts like "$1,234.50", "-12", or accounting negatives "(12.00)"."""
    s = text.strip().replace("$", "").replace(",", "")
    if s.startswith("(") and s.endswith(")"):
        s = s[1:-1]
    try:
        return Decimal(s)
    except InvalidOperation as e:
        raise ValueError(f"not an amount: {text!r}") from e


def balance(lines: list[str]) -> Decimal:
    """Sum a list of amount strings."""
    return sum((parse_amount(x) for x in lines), Decimal("0"))


def format_amount(value: Decimal) -> str:
    """Format using accounting style: negatives in parentheses, two decimals."""
    q = value.quantize(Decimal("0.01"))
    body = f"${abs(q):,.2f}"
    return f"({body})" if q < 0 else body
