"""Data types."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Line:
    sku: str
    unit_price: Decimal
    qty: int
    category: str
