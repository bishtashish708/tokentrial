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


# --- Hidden spec checks --------------------------------------------------------


def _one(price, qty, cat="toys"):
    return [Line("x", Decimal(price), qty, cat)]


@pytest.mark.parametrize("qty,expected", [(9, "90.00"), (10, "95.00"), (49, "465.50"),
                                          (50, "450.00"), (51, "459.00")])
def test_quantity_break_boundaries(qty, expected):
    assert price_order(_one("10.00", qty), [], "OR")["subtotal"] == Decimal(expected)


def test_half_cent_rounds_up():
    # 0.125 * 1 -> 0.13 (half up), not 0.12 (banker's)
    assert price_order(_one("0.125", 1), [], "OR")["subtotal"] == Decimal("0.13")


def test_percent_codes_apply_before_fixed_regardless_of_order():
    a = price_order(_one("100.00", 1), ["FIVEOFF", "SAVE10"], "OR")
    b = price_order(_one("100.00", 1), ["SAVE10", "FIVEOFF"], "OR")
    assert a["discounted"] == b["discounted"] == Decimal("85.00")


def test_percent_codes_compound():
    r = price_order(_one("100.00", 1), ["SAVE10", "SAVE10"], "OR")
    assert r["discounted"] == Decimal("81.00")


def test_never_below_zero():
    r = price_order(_one("3.00", 1), ["WELCOME", "FIVEOFF"], "CA")
    assert r["discounted"] == Decimal("0.00") and r["tax"] == Decimal("0.00")


@pytest.mark.parametrize("cat", ["Food", " BOOKS ", "food", "Books\t"])
def test_exempt_categories_ignore_case_and_whitespace(cat):
    assert price_order(_one("20.00", 1, cat), [], "NY")["tax"] == Decimal("0.00")


def test_mixed_exempt_and_taxable_after_discount():
    lines = [Line("a", Decimal("60.00"), 1, "Food"), Line("b", Decimal("40.00"), 1, "toys")]
    r = price_order(lines, ["SAVE10"], "WA")
    # discounted 90.00; taxable share 40/100 -> base 36.00; 36 * 0.065 = 2.34
    assert r["tax"] == Decimal("2.34") and r["total"] == Decimal("92.34")
