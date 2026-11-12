"""Regional tax rates."""

from decimal import Decimal

RATES = {"CA": Decimal("0.0725"), "NY": Decimal("0.08875"), "OR": Decimal("0"),
         "TX": Decimal("0.0625"), "WA": Decimal("0.065")}
EXEMPT_CATEGORIES = {"food", "books"}
