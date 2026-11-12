"""Generate tasks/py-pytest-cart-pricing deterministically.

Usage: python3 scripts/make_cart_task.py

Writes the buggy repo, the reference solution, visible tests (with a golden CSV
computed by the reference implementation) and hidden tests.
"""

import csv
import io
import random
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "tasks" / "py-pytest-cart-pricing"

SPEC = """# cartcalc pricing specification

All money is `decimal.Decimal`. "Round" always means: round to whole cents,
halves away from zero (ROUND_HALF_UP). Never use binary floats for money.

1. **Line subtotal.** `unit_price * qty`, with quantity breaks on the unit price:
   qty of 10 or more: 5% off; qty of 50 or more: 10% off (not cumulative).
   Round the line subtotal.
2. **Order subtotal.** Sum of line subtotals.
3. **Discount codes**, applied to the order subtotal:
   - All percentage codes apply first, compounding, in the order given
     (two 10% codes take 19% off in total). Round after each one.
   - Then fixed-amount codes are subtracted, in the order given.
   - The result never goes below 0.00.
4. **Tax.** Each region has a rate (see `cartcalc/tax.py`). Lines whose category
   is exempt (`food`, `books`) are not taxed; category matching ignores case and
   surrounding whitespace. The taxable base is the discounted subtotal multiplied
   by (sum of taxable line subtotals / order subtotal). Tax = round(base * rate).
   An empty order or a zero order subtotal has zero tax.
5. **Total** = discounted subtotal + tax.

Unknown discount codes and unknown regions raise `ValueError`.
"""

CODES = '''"""Discount codes."""

from decimal import Decimal

PERCENT = {"SAVE10": Decimal("10"), "SAVE15": Decimal("15"), "VIP5": Decimal("5")}
FIXED = {"FIVEOFF": Decimal("5.00"), "WELCOME": Decimal("12.50")}
'''

TAX = '''"""Regional tax rates."""

from decimal import Decimal

RATES = {"CA": Decimal("0.0725"), "NY": Decimal("0.08875"), "OR": Decimal("0"),
         "TX": Decimal("0.0625"), "WA": Decimal("0.065")}
EXEMPT_CATEGORIES = {"food", "books"}
'''

MODEL = '''"""Data types."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Line:
    sku: str
    unit_price: Decimal
    qty: int
    category: str
'''

INIT = '''"""cartcalc: order pricing. See SPEC.md."""

from cartcalc.engine import price_order

__all__ = ["price_order"]
'''

ENGINE_FIXED = '''"""Order pricing engine. See SPEC.md for the rules."""

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
'''

# Four bugs: float rounding (banker's + binary floats), quantity-break boundaries,
# discount application order, and case-sensitive exemption matching.
ENGINE_BUGGY = (
    ENGINE_FIXED.replace(
        """def money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)""",
        """def money(value: Decimal) -> Decimal:
    return Decimal(str(round(float(value), 2))).quantize(CENT)""",
    )
    .replace("    if line.qty >= 50:", "    if line.qty > 50:")
    .replace("    elif line.qty >= 10:", "    elif line.qty > 10:")
    .replace(
        """    amount = subtotal
    for code in (c for c in codes if c in PERCENT):
        amount = money(amount * (1 - PERCENT[code] / 100))
    for code in (c for c in codes if c in FIXED):
        amount = amount - FIXED[code]""",
        """    amount = subtotal
    for code in codes:
        if code in PERCENT:
            amount = money(amount * (1 - PERCENT[code] / 100))
        else:
            amount = amount - FIXED[code]""",
    )
    .replace(
        "    return category.strip().lower() in EXEMPT_CATEGORIES",
        "    return category in EXEMPT_CATEGORIES",
    )
    .replace("from decimal import ROUND_HALF_UP, Decimal", "from decimal import Decimal")
)
assert ENGINE_BUGGY.count("Decimal(str(round(") == 1 and "> 50" in ENGINE_BUGGY

VISIBLE_TESTS = '''"""Tests for cartcalc. Golden cases are in tests/golden_orders.csv."""

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
'''

HIDDEN_EXTRA = """

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


@pytest.mark.parametrize("cat", ["Food", " BOOKS ", "food", "Books\\t"])
def test_exempt_categories_ignore_case_and_whitespace(cat):
    assert price_order(_one("20.00", 1, cat), [], "NY")["tax"] == Decimal("0.00")


def test_mixed_exempt_and_taxable_after_discount():
    lines = [Line("a", Decimal("60.00"), 1, "Food"), Line("b", Decimal("40.00"), 1, "toys")]
    r = price_order(lines, ["SAVE10"], "WA")
    # discounted 90.00; taxable share 40/100 -> base 36.00; 36 * 0.065 = 2.34
    assert r["tax"] == Decimal("2.34") and r["total"] == Decimal("92.34")
"""

CHECK = """#!/usr/bin/env bash
# Hidden check for py-pytest-cart-pricing: restore the original tests and golden
# file, add hidden spec tests, run everything.
set -euo pipefail
: "${TASK_DIR:?TASK_DIR must point at the task directory}"
rm -rf tests && mkdir -p tests
cp "$TASK_DIR"/hidden_tests/* tests/
python3 -m pytest -q -p no:cacheprovider tests >/dev/null 2>&1
"""

TASK_TOML = '''prompt = """
The test suite for `cartcalc` is failing. The pricing rules are specified in SPEC.md.
Fix the source code under cartcalc/ so that it implements SPEC.md exactly. Do not modify the
tests or the golden data in tests/. Run the tests with `python3 -m pytest tests`.
Your fix will also be checked against additional tests derived from SPEC.md.
"""
timeout_s = 1200
requires = ["pytest"]
tags = ["python", "pytest", "large-test-output", "multi-bug", "spec"]
'''


def reference():
    ns = {}
    src = ENGINE_FIXED
    for mod, code in (("cartcalc.codes", CODES), ("cartcalc.tax", TAX), ("cartcalc.model", MODEL)):
        m = type(sys)(mod)
        exec(code, m.__dict__)
        sys.modules[mod] = m
    exec(src, ns)
    return ns["price_order"], sys.modules["cartcalc.model"].Line


def golden_rows(price_order, Line):
    from decimal import Decimal

    rng = random.Random(4242)
    cats = ["toys", "food", "books", "garden", "Food", "BOOKS", "electronics", " food"]
    codes = ["SAVE10", "SAVE15", "VIP5", "FIVEOFF", "WELCOME"]
    regions = ["CA", "NY", "OR", "TX", "WA"]
    qtys = [1, 2, 3, 9, 10, 11, 25, 49, 50, 51, 75]
    rows = []
    for i in range(150):
        lines = []
        for j in range(rng.randint(1, 4)):
            cents = rng.choice([rng.randint(50, 9999), rng.randint(50, 999)])
            price = f"{cents // 100}.{cents % 100:02d}"
            if rng.random() < 0.25:
                price += "5"  # half-cent unit prices exercise rounding
            lines.append([f"sku{i}-{j}", price, rng.choice(qtys), rng.choice(cats)])
        cs = rng.sample(codes, rng.randint(0, 3))
        region = rng.choice(regions)
        r = price_order([Line(s, Decimal(p), q, c) for s, p, q, c in lines], cs, region)
        rows.append(
            {
                "id": f"order{i:03d}",
                "lines": __import__("json").dumps(lines),
                "codes": __import__("json").dumps(cs),
                "region": region,
                **{k: str(v) for k, v in r.items()},
            }
        )
    return rows


def main():
    price_order, Line = reference()
    rows = golden_rows(price_order, Line)
    for d in ("repo", "solution", "hidden_tests"):
        shutil.rmtree(ROOT / d, ignore_errors=True)
    pkg = ROOT / "repo" / "cartcalc"
    pkg.mkdir(parents=True)
    for name, code in (
        ("__init__.py", INIT),
        ("codes.py", CODES),
        ("tax.py", TAX),
        ("model.py", MODEL),
        ("engine.py", ENGINE_BUGGY),
    ):
        (pkg / name).write_text(code)
    (ROOT / "repo" / "SPEC.md").write_text(SPEC)
    (ROOT / "repo" / "tests").mkdir()
    (ROOT / "repo" / "tests" / "test_cartcalc.py").write_text(VISIBLE_TESTS)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    (ROOT / "repo" / "tests" / "golden_orders.csv").write_text(buf.getvalue())
    (ROOT / "solution" / "cartcalc").mkdir(parents=True)
    (ROOT / "solution" / "cartcalc" / "engine.py").write_text(ENGINE_FIXED)
    (ROOT / "hidden_tests").mkdir()
    (ROOT / "hidden_tests" / "test_cartcalc.py").write_text(VISIBLE_TESTS + HIDDEN_EXTRA)
    (ROOT / "hidden_tests" / "golden_orders.csv").write_text(buf.getvalue())
    (ROOT / "check.sh").write_text(CHECK)
    (ROOT / "check.sh").chmod(0o755)
    (ROOT / "task.toml").write_text(TASK_TOML)


if __name__ == "__main__":
    main()
