"""Tests for cartcalc. Golden cases are in tests/golden_orders.csv."""

import csv
import json
from decimal import Decimal
from pathlib import Path

import pytest

from cartcalc import price_order
from cartcalc.model import Line

GOLDEN = Path(__file__).parent / "golden_orders.csv"


def _load():
    with GOLDEN.open() as f:
        for row in csv.DictReader(f):
            lines = [Line(sku, Decimal(p), int(q), c) for sku, p, q, c in json.loads(row["lines"])]
            yield pytest.param(lines, json.loads(row["codes"]), row["region"],
                               {k: Decimal(row[k]) for k in ("subtotal", "discounted", "tax", "total")},
                               id=row["id"])


@pytest.mark.parametrize("lines,codes,region,expected", list(_load()))
def test_golden_order(lines, codes, region, expected):
    assert price_order(lines, codes, region) == expected


def test_unknown_code():
    with pytest.raises(ValueError):
        price_order([Line("a", Decimal("1.00"), 1, "toys")], ["NOPE"], "CA")


def test_unknown_region():
    with pytest.raises(ValueError):
        price_order([Line("a", Decimal("1.00"), 1, "toys")], [], "ZZ")


def test_empty_order():
    assert price_order([], [], "NY")["total"] == Decimal("0.00")
