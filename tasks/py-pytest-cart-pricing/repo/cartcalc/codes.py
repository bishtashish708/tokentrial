"""Discount codes."""

from decimal import Decimal

PERCENT = {"SAVE10": Decimal("10"), "SAVE15": Decimal("15"), "VIP5": Decimal("5")}
FIXED = {"FIVEOFF": Decimal("5.00"), "WELCOME": Decimal("12.50")}
