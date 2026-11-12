"""Generate tasks/sql-monthly-revenue deterministically.

Usage: python3 scripts/make_sql_revenue_task.py

The repo is a small SQLite analytics project whose `reports/monthly_revenue.sql` is wrong
in four ways (see BUGGY_SQL). Visible unittest tests run the report on a small hand-made
fixture; the hidden check also runs it on a larger seeded dataset whose expected rows come
from a pure-Python reference (Decimal arithmetic, datetime parsing, no SQL). The generator
cross-checks that reference against the reference SQL (an independent computation done by
SQLite) for both datasets, asserts the buggy SQL fails, and asserts that several plausible
partial fixes pass the visible tests but fail the hidden dataset.
"""

import json
import random
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "tasks" / "sql-monthly-revenue"
SEED = 20261112

# --------------------------------------------------------------------------- repo files

SCHEMA = """\
-- Schema for the storefront analytics warehouse (SQLite).
-- Loaded by run_report.py, scripts/seed_demo_db.py and the tests.

CREATE TABLE customers (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL,
    region      TEXT    NOT NULL,              -- sales region code, e.g. 'NA', 'EMEA'
    is_test     INTEGER NOT NULL DEFAULT 0     -- 1 = internal/QA account
);

CREATE TABLE orders (
    id          INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    ordered_at  TEXT    NOT NULL,              -- ISO 8601 with UTC offset, see SPEC.md
    currency    TEXT    NOT NULL,              -- ISO 4217 code
    status      TEXT    NOT NULL
                CHECK (status IN ('pending', 'paid', 'shipped', 'cancelled'))
);

CREATE TABLE order_lines (
    id               INTEGER PRIMARY KEY,
    order_id         INTEGER NOT NULL REFERENCES orders(id),
    sku              TEXT    NOT NULL,
    quantity         INTEGER NOT NULL CHECK (quantity > 0),
    unit_price_cents INTEGER NOT NULL CHECK (unit_price_cents >= 0)  -- order currency
);

CREATE TABLE refunds (
    id           INTEGER PRIMARY KEY,
    order_id     INTEGER NOT NULL REFERENCES orders(id),
    refunded_at  TEXT    NOT NULL,             -- ISO 8601 with UTC offset
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),            -- order currency
    reason       TEXT
);

CREATE TABLE fx_rates (
    currency       TEXT NOT NULL,
    effective_date TEXT NOT NULL,              -- YYYY-MM-DD; rate applies from this date on
    usd_per_unit   REAL NOT NULL,              -- 1 unit of `currency` = usd_per_unit USD
    PRIMARY KEY (currency, effective_date)
);

CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_lines_order ON order_lines(order_id);
CREATE INDEX idx_refunds_order ON refunds(order_id);
"""

SPEC = """\
# Report specification: `monthly_revenue`

`reports/monthly_revenue.sql` produces **net revenue in USD per region per calendar month**.
It must be a single SQLite `SELECT` statement (CTEs allowed) that runs against a database
created from `schema.sql`, with no parameters.

## Output

Exactly three columns, in this order and with these names:

| column            | type    | meaning                                         |
|-------------------|---------|-------------------------------------------------|
| `month`           | TEXT    | calendar month in UTC, formatted `YYYY-MM`      |
| `region`          | TEXT    | `customers.region` of the order's customer      |
| `net_revenue_usd` | REAL    | net revenue in USD, rounded to 2 decimals       |

Rows are ordered by `month` ascending, then `region` ascending.

## Which records count

* Orders whose `status` is `'cancelled'` are excluded entirely: neither their order lines
  nor any refunds recorded against them count. Every other status counts.
* Orders placed by test accounts (`customers.is_test = 1`) are excluded entirely, lines
  and refunds alike.

## Amounts

* Each order line contributes `quantity * unit_price_cents` (minor units of the order's
  currency, i.e. hundredths of a unit).
* Each refund contributes `-amount_cents` (also in the order's currency).
* Amounts are converted to USD with `fx_rates.usd_per_unit` for the order's currency,
  using **the rate effective on the order date**: the row with the latest
  `effective_date` that is on or before the UTC calendar date of `orders.ordered_at`.
  Refunds use the same rate as their order (the order-date rate, not a refund-date rate).
  USD has its own rows in `fx_rates` (rate 1). Every counted order has an applicable rate.

## Which month

* Timestamps (`ordered_at`, `refunded_at`) are ISO 8601 strings that carry a UTC offset
  (`Z`, `+05:30`, `-08:00`, ...). All months and dates in this report are taken **in UTC**,
  e.g. `2024-03-31T22:30:00-05:00` is in month `2024-04`.
* An order line belongs to the month of its order's `ordered_at`.
* A refund belongs to the month of its own `refunded_at`, not the month of the order.

## Aggregation and rounding

* `net_revenue_usd` for a (month, region) is the sum, over all counted order lines and
  refunds in that month and region, of their USD amounts, divided by 100 to get dollars.
* Round **once**, at the end, to 2 decimal places (half away from zero). Do not round
  individual lines, orders or refunds.
* A (month, region) row appears if and only if at least one counted order line or counted
  refund falls in it. Months with no activity are omitted (no zero-filled rows). A row
  whose activity nets to zero (or below) still appears, with its value (e.g. `0.0`,
  `-12.5`).
"""

README = """\
# storefront-analytics

SQL reports over the storefront warehouse (SQLite). Each report is a single `SELECT` in
`reports/`; `run_report.py` runs one against a database and prints the result.

```
python3 scripts/seed_demo_db.py demo.db          # build a random demo database
python3 run_report.py --db demo.db monthly_revenue
python3 run_report.py --db demo.db top_customers --format table
```

Report definitions live next to the SQL; the finance-facing `monthly_revenue` report is
specified in SPEC.md.

Tests: `python3 -m unittest discover -s tests`
"""

RUN_REPORT = '''\
#!/usr/bin/env python3
"""Run one of the SQL reports in reports/ against a SQLite database."""

import argparse
import csv
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPORTS = HERE / "reports"


def available_reports():
    return sorted(p.stem for p in REPORTS.glob("*.sql"))


def load_sql(name):
    path = REPORTS / f"{name}.sql"
    if not path.exists():
        raise SystemExit(f"unknown report {name!r}; available: {', '.join(available_reports())}")
    return path.read_text()


def run_sql(conn, sql):
    """Execute a report and return (column_names, rows)."""
    cur = conn.execute(sql)
    columns = [d[0] for d in cur.description]
    return columns, cur.fetchall()


def print_table(columns, rows, out=sys.stdout):
    cells = [[str(c) for c in columns]] + [["" if v is None else str(v) for v in r] for r in rows]
    widths = [max(len(row[i]) for row in cells) for i in range(len(columns))]
    for n, row in enumerate(cells):
        out.write("  ".join(v.ljust(w) for v, w in zip(row, widths)).rstrip() + "\\n")
        if n == 0:
            out.write("  ".join("-" * w for w in widths) + "\\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("report", help="report name (file stem in reports/)")
    ap.add_argument("--db", required=True, help="path to the SQLite database")
    ap.add_argument("--format", choices=["csv", "table"], default="csv")
    args = ap.parse_args(argv)

    conn = sqlite3.connect(args.db)
    try:
        columns, rows = run_sql(conn, load_sql(args.report))
    finally:
        conn.close()
    if args.format == "table":
        print_table(columns, rows)
    else:
        w = csv.writer(sys.stdout)
        w.writerow(columns)
        w.writerows(rows)


if __name__ == "__main__":
    main()
'''

SEED_DEMO = '''\
#!/usr/bin/env python3
"""Build a random demo database for poking at the reports by hand.

Usage: python3 scripts/seed_demo_db.py demo.db [--seed N]
"""

import argparse
import random
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
REGIONS = ["NA", "EMEA", "APAC", "LATAM"]
CURRENCIES = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27, "CAD": 0.74}
OFFSETS = [-8, -5, 0, 1, 9]


def stamp(dt_utc, offset_h):
    local = dt_utc.astimezone(timezone(timedelta(hours=offset_h)))
    return local.isoformat(timespec="seconds")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("db")
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    path = Path(args.db)
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    conn.executescript((HERE / "schema.sql").read_text())

    for cur, base in CURRENCIES.items():
        day = datetime(2023, 12, 1)
        while day < datetime(2025, 1, 1):
            rate = 1.0 if cur == "USD" else round(base * rng.uniform(0.97, 1.03), 4)
            conn.execute("INSERT INTO fx_rates VALUES (?, ?, ?)", (cur, day.date().isoformat(), rate))
            day += timedelta(days=rng.randint(7, 21) if cur != "USD" else 400)

    for cid in range(1, 41):
        conn.execute(
            "INSERT INTO customers VALUES (?, ?, ?, ?)",
            (cid, f"Customer {cid}", rng.choice(REGIONS), int(rng.random() < 0.1)),
        )
    line_id = refund_id = 0
    for oid in range(1, 401):
        when = datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=rng.randrange(525600))
        status = rng.choices(["paid", "shipped", "pending", "cancelled"], [5, 8, 1, 1])[0]
        conn.execute(
            "INSERT INTO orders VALUES (?, ?, ?, ?, ?)",
            (oid, rng.randint(1, 40), stamp(when, rng.choice(OFFSETS)), rng.choice(list(CURRENCIES)), status),
        )
        for _ in range(rng.randint(1, 3)):
            line_id += 1
            conn.execute(
                "INSERT INTO order_lines VALUES (?, ?, ?, ?, ?)",
                (line_id, oid, f"SKU-{rng.randint(100, 999)}", rng.randint(1, 4), rng.randint(199, 9999)),
            )
        if rng.random() < 0.2:
            refund_id += 1
            later = when + timedelta(days=rng.randint(1, 60))
            conn.execute(
                "INSERT INTO refunds VALUES (?, ?, ?, ?, ?)",
                (refund_id, oid, stamp(later, rng.choice(OFFSETS)), rng.randint(100, 5000), "customer request"),
            )
    conn.commit()
    conn.close()
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
'''

TOP_CUSTOMERS_SQL = """\
-- Top 20 customers by gross order value (order currency, no FX), all time.
-- Used by the account-management team; not finance-grade.
SELECT
    c.id   AS customer_id,
    c.name AS customer_name,
    c.region,
    COUNT(DISTINCT o.id)                       AS orders,
    SUM(ol.quantity * ol.unit_price_cents)     AS gross_cents
FROM customers c
JOIN orders o       ON o.customer_id = c.id
JOIN order_lines ol ON ol.order_id = o.id
WHERE o.status <> 'cancelled'
  AND c.is_test = 0
GROUP BY c.id, c.name, c.region
ORDER BY gross_cents DESC, c.id
LIMIT 20;
"""

REFUND_REASONS_SQL = """\
-- Refund count and total (order currency) by reason, for the support dashboard.
SELECT
    COALESCE(r.reason, '(none)') AS reason,
    COUNT(*)                     AS refunds,
    SUM(r.amount_cents)          AS total_cents
FROM refunds r
GROUP BY COALESCE(r.reason, '(none)')
ORDER BY refunds DESC, reason;
"""

BUGGY_SQL = """\
-- Monthly net revenue (USD) by region. Definition: SPEC.md.
-- Owner: finance-analytics. Feeds the monthly board pack.
SELECT
    substr(o.ordered_at, 1, 7)                       AS month,
    c.region                                         AS region,
    ROUND(
        (SUM(ol.quantity * ol.unit_price_cents * fx.usd_per_unit)
         - COALESCE(SUM(rf.amount_cents * fx.usd_per_unit), 0)) / 100.0,
        2
    )                                                AS net_revenue_usd
FROM orders o
JOIN customers c    ON c.id = o.customer_id
JOIN order_lines ol ON ol.order_id = o.id
LEFT JOIN refunds rf ON rf.order_id = o.id
JOIN fx_rates fx    ON fx.currency = o.currency
                   AND fx.effective_date = (SELECT MAX(effective_date)
                                            FROM fx_rates
                                            WHERE currency = o.currency)
WHERE o.status <> 'cancelled'
GROUP BY month, c.region
ORDER BY month, c.region;
"""

SOLUTION_SQL = """\
-- Monthly net revenue (USD) by region. Definition: SPEC.md.
-- Owner: finance-analytics. Feeds the monthly board pack.
WITH counted_orders AS (
    SELECT
        o.id,
        c.region,
        o.ordered_at,
        (SELECT fx.usd_per_unit
           FROM fx_rates fx
          WHERE fx.currency = o.currency
            AND fx.effective_date <= date(o.ordered_at)
          ORDER BY fx.effective_date DESC
          LIMIT 1) AS rate
    FROM orders o
    JOIN customers c ON c.id = o.customer_id
    WHERE o.status <> 'cancelled'
      AND c.is_test = 0
),
amounts AS (
    SELECT co.region,
           strftime('%Y-%m', co.ordered_at) AS month,
           ol.quantity * ol.unit_price_cents * co.rate AS usd_cents
    FROM counted_orders co
    JOIN order_lines ol ON ol.order_id = co.id
    UNION ALL
    SELECT co.region,
           strftime('%Y-%m', rf.refunded_at) AS month,
           -rf.amount_cents * co.rate AS usd_cents
    FROM counted_orders co
    JOIN refunds rf ON rf.order_id = co.id
)
SELECT
    month,
    region,
    ROUND(SUM(usd_cents) / 100.0, 2) AS net_revenue_usd
FROM amounts
GROUP BY month, region
ORDER BY month, region;
"""

# Plausible partial fixes: each must pass the visible tests but fail the hidden dataset.
PARTIAL_FIXES = {
    "fx lookup uses local date": ("date(o.ordered_at)", "substr(o.ordered_at, 1, 10)"),
    "refunds of cancelled orders counted": (
        "JOIN refunds rf ON rf.order_id = co.id",
        "JOIN refunds rf ON rf.order_id = co.id\n    UNION ALL\n"
        "    SELECT c.region, strftime('%Y-%m', rf.refunded_at),\n"
        "           -rf.amount_cents * (SELECT fx.usd_per_unit FROM fx_rates fx\n"
        "             WHERE fx.currency = o.currency AND fx.effective_date <= date(o.ordered_at)\n"
        "             ORDER BY fx.effective_date DESC LIMIT 1)\n"
        "    FROM refunds rf JOIN orders o ON o.id = rf.order_id\n"
        "    JOIN customers c ON c.id = o.customer_id\n"
        "    WHERE o.status = 'cancelled' AND c.is_test = 0",
    ),
    "rounds each line": (
        "ol.quantity * ol.unit_price_cents * co.rate AS usd_cents",
        "ROUND(ol.quantity * ol.unit_price_cents * co.rate) AS usd_cents",
    ),
    "refund month in local time": (
        "strftime('%Y-%m', rf.refunded_at)",
        "substr(rf.refunded_at, 1, 7)",
    ),
    "refunds use refund-date rate": (
        "-rf.amount_cents * co.rate AS usd_cents",
        "-rf.amount_cents * (SELECT fx.usd_per_unit FROM fx_rates fx JOIN orders o2 ON o2.id = co.id\n"
        "             WHERE fx.currency = o2.currency AND fx.effective_date <= date(rf.refunded_at)\n"
        "             ORDER BY fx.effective_date DESC LIMIT 1) AS usd_cents",
    ),
}

# Partial fixes the visible fixture is allowed to catch too.
VISIBLE_CATCHES = {"refunds use refund-date rate"}

# --------------------------------------------------------------------------- fixture

# Small hand-written fixture for the visible tests. Exercises: UTC month boundary on an
# order, refund in a later month (and in a month with no orders for that region), an order
# with several lines and a refund (fan-out), a test account, a cancelled order, two EUR
# rates (order before the latest rate), USD rate rows, and a pending order.
FIXTURE_SQL = """\
-- Fixture for tests/test_monthly_revenue.py (loaded after schema.sql).
INSERT INTO fx_rates VALUES ('USD', '2020-01-01', 1.0);
INSERT INTO fx_rates VALUES ('EUR', '2024-01-01', 1.10);
INSERT INTO fx_rates VALUES ('EUR', '2024-02-15', 1.08);
INSERT INTO fx_rates VALUES ('EUR', '2024-04-01', 1.05);
INSERT INTO fx_rates VALUES ('GBP', '2024-01-01', 1.27);

INSERT INTO customers VALUES (1, 'Acme Corp',      'NA',   0);
INSERT INTO customers VALUES (2, 'Brightline GmbH', 'EMEA', 0);
INSERT INTO customers VALUES (3, 'QA Bot',          'NA',   1);
INSERT INTO customers VALUES (4, 'Northwind Ltd',   'EMEA', 0);

-- Acme: January order, two lines, refunded in February.
INSERT INTO orders VALUES (1, 1, '2024-01-10T09:00:00-05:00', 'USD', 'shipped');
INSERT INTO order_lines VALUES (1, 1, 'SKU-100', 2, 1500);
INSERT INTO order_lines VALUES (2, 1, 'SKU-101', 1, 4999);
INSERT INTO refunds VALUES (1, 1, '2024-02-02T12:00:00Z', 1500, 'damaged');

-- Acme: placed on Jan 31 local time, which is already February in UTC.
INSERT INTO orders VALUES (2, 1, '2024-01-31T21:30:00-05:00', 'USD', 'paid');
INSERT INTO order_lines VALUES (3, 2, 'SKU-102', 3, 1000);

-- Brightline: EUR order in January (rate 1.10), refunded in March (still 1.10).
INSERT INTO orders VALUES (3, 2, '2024-01-20T10:00:00+01:00', 'EUR', 'shipped');
INSERT INTO order_lines VALUES (4, 3, 'SKU-200', 1, 10000);
INSERT INTO order_lines VALUES (5, 3, 'SKU-201', 4, 2500);
INSERT INTO refunds VALUES (2, 3, '2024-03-05T08:00:00+01:00', 2000, 'late delivery');

-- Brightline: EUR order in March (rate 1.08), pending.
INSERT INTO orders VALUES (4, 2, '2024-03-02T15:45:00+01:00', 'EUR', 'pending');
INSERT INTO order_lines VALUES (6, 4, 'SKU-202', 1, 3333);

-- Northwind: GBP order in February, cancelled (does not count).
INSERT INTO orders VALUES (5, 4, '2024-02-10T11:00:00Z', 'GBP', 'cancelled');
INSERT INTO order_lines VALUES (7, 5, 'SKU-300', 1, 8000);

-- Northwind: GBP order in February that counts.
INSERT INTO orders VALUES (6, 4, '2024-02-11T11:00:00Z', 'GBP', 'paid');
INSERT INTO order_lines VALUES (8, 6, 'SKU-301', 2, 1999);

-- QA Bot: test account, does not count.
INSERT INTO orders VALUES (7, 3, '2024-02-03T10:00:00-08:00', 'USD', 'paid');
INSERT INTO order_lines VALUES (9, 7, 'SKU-100', 10, 1500);
"""

VISIBLE_TEST_TEMPLATE = '''\
"""Tests for reports/monthly_revenue.sql on a small fixture (see SPEC.md)."""

import sqlite3
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

EXPECTED = __EXPECTED__


def run_report(fixture_sql):
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript((ROOT / "schema.sql").read_text())
        conn.executescript(fixture_sql)
        cur = conn.execute((ROOT / "reports" / "monthly_revenue.sql").read_text())
        columns = [d[0] for d in cur.description]
        return columns, cur.fetchall()
    finally:
        conn.close()


class MonthlyRevenueTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.columns, cls.rows = run_report((HERE / "fixture.sql").read_text())

    def test_columns(self):
        self.assertEqual(self.columns, ["month", "region", "net_revenue_usd"])

    def test_months_and_regions(self):
        self.assertEqual([(r[0], r[1]) for r in self.rows], [(m, g) for m, g, _ in EXPECTED])

    def test_values(self):
        got = [(r[0], r[1], round(float(r[2]), 2)) for r in self.rows]
        self.assertEqual(got, EXPECTED)

    def test_refund_lands_in_refund_month(self):
        rows = {(r[0], r[1]): round(float(r[2]), 2) for r in self.rows}
        self.assertIn(("2024-03", "EMEA"), rows)
        self.assertNotIn(("2024-01", "QA"), rows)


if __name__ == "__main__":
    unittest.main()
'''

HIDDEN_TEST = '''\
"""Hidden: reports/monthly_revenue.sql on a larger seeded dataset (expected rows from a
pure-Python reference implementation of SPEC.md)."""

import json
import sqlite3
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


class HiddenDatasetTest(unittest.TestCase):
    def test_hidden_dataset(self):
        conn = sqlite3.connect(":memory:")
        conn.executescript((HERE / "hidden_schema.sql").read_text())
        conn.executescript((HERE / "hidden_data.sql").read_text())
        cur = conn.execute((ROOT / "reports" / "monthly_revenue.sql").read_text())
        columns = [d[0] for d in cur.description]
        rows = cur.fetchall()
        conn.close()
        self.assertEqual(columns, ["month", "region", "net_revenue_usd"])
        expected = json.loads((HERE / "hidden_expected.json").read_text())
        self.assertEqual(len(rows), len(expected))
        for got, (month, region, cents) in zip(rows, expected):
            self.assertEqual((got[0], got[1]), (month, region))
            self.assertIsNotNone(got[2])
            # the report must already be rounded to cents
            self.assertAlmostEqual(float(got[2]) * 100, cents, delta=1e-6, msg=(month, region))


if __name__ == "__main__":
    unittest.main()
'''

CHECK = """\
#!/usr/bin/env bash
# Hidden check for sql-monthly-revenue: restore the visible tests and fixture, add the
# hidden seeded dataset, and run everything against the agent's reports/monthly_revenue.sql.
set -euo pipefail
: "${TASK_DIR:?TASK_DIR must point at the task directory}"
[ -f reports/monthly_revenue.sql ] || exit 1
rm -rf tests && mkdir -p tests
cp "$TASK_DIR"/hidden_tests/* tests/
python3 -m unittest discover -s tests >/dev/null 2>&1
"""

TASK_TOML = '''\
prompt = """
`reports/monthly_revenue.sql` in this SQLite analytics repository produces the wrong numbers.
SPEC.md defines exactly what the report must return. Fix reports/monthly_revenue.sql so that
it implements SPEC.md exactly; that file is the deliverable (it must stay a single SELECT
statement). Do not modify the tests, the fixture or schema.sql. Run the tests with
`python3 -m unittest discover -s tests`. Your fix will also be checked against additional
cases derived from SPEC.md, on a larger dataset.
"""
timeout_s = 1200
tags = ["sql", "sqlite", "python", "spec", "multi-bug", "hard"]
'''

# --------------------------------------------------------------------------- reference


def parse_ts(text):
    dt = datetime.fromisoformat(text)
    assert dt.tzinfo is not None, text
    return dt.astimezone(UTC)


def reference_report(db):
    """Pure-Python implementation of SPEC.md: reads raw tables, no SQL logic.

    Returns [(month, region, exact Decimal dollars)] sorted by month, region.
    """
    tables = {}
    for name in ("customers", "orders", "order_lines", "refunds"):
        cur = db.execute(f"SELECT * FROM {name}")
        cols = [d[0] for d in cur.description]
        tables[name] = [dict(zip(cols, row)) for row in cur.fetchall()]
    # Rates as exact decimals: read their text form (the generator writes <= 4 decimals).
    rates = defaultdict(list)
    for cur_code, eff, rate_text in db.execute(
        "SELECT currency, effective_date, CAST(usd_per_unit AS TEXT) FROM fx_rates"
    ):
        rates[cur_code].append((date.fromisoformat(eff), Decimal(rate_text)))
    for lst in rates.values():
        lst.sort()

    def rate_for(currency, day):
        best = None
        for eff, rate in rates[currency]:
            if eff <= day:
                best = rate
        assert best is not None, (currency, day)
        return best

    customers = {c["id"]: c for c in tables["customers"]}
    counted = {}
    for o in tables["orders"]:
        cust = customers[o["customer_id"]]
        if o["status"] == "cancelled" or cust["is_test"]:
            continue
        placed = parse_ts(o["ordered_at"])
        counted[o["id"]] = (cust["region"], placed, rate_for(o["currency"], placed.date()))

    totals = defaultdict(Decimal)
    for line in tables["order_lines"]:
        if line["order_id"] in counted:
            region, placed, rate = counted[line["order_id"]]
            key = (placed.strftime("%Y-%m"), region)
            totals[key] += Decimal(line["quantity"] * line["unit_price_cents"]) * rate
    for rf in tables["refunds"]:
        if rf["order_id"] in counted:
            region, _, rate = counted[rf["order_id"]]
            key = (parse_ts(rf["refunded_at"]).strftime("%Y-%m"), region)
            totals[key] -= Decimal(rf["amount_cents"]) * rate
    return [(m, r, totals[(m, r)] / 100) for m, r in sorted(totals)]


def round_cents(dollars):
    """Half away from zero, to whole cents (int)."""
    q = abs(dollars).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int((q * 100).to_integral_value()) * (1 if dollars >= 0 else -1)


def build_db(*scripts):
    db = sqlite3.connect(":memory:")
    for s in scripts:
        db.executescript(s)
    return db


def run_sql(db, sql):
    cur = db.execute(sql)
    return [d[0] for d in cur.description], cur.fetchall()


def sql_matches(db, sql, expected_cents):
    try:
        cols, rows = run_sql(db, sql)
    except sqlite3.Error:
        return False
    if cols != ["month", "region", "net_revenue_usd"] or len(rows) != len(expected_cents):
        return False
    for got, (m, r, c) in zip(rows, expected_cents):
        if (got[0], got[1]) != (m, r) or got[2] is None or abs(float(got[2]) * 100 - c) > 1e-6:
            return False
    return True


# --------------------------------------------------------------------------- hidden data

REGIONS = ["APAC", "EMEA", "LATAM", "NA"]
OFFSETS = [
    timedelta(hours=h, minutes=m)
    for h, m in [(-8, 0), (-5, 0), (0, 0), (1, 0), (5, 30), (9, 0), (-3, 0)]
]


def stamp(dt_utc, offset, rng):
    if offset == timedelta(0) and rng.random() < 0.5:
        return dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    return dt_utc.astimezone(timezone(offset)).isoformat(timespec="seconds")


def make_hidden_dataset(seed):
    rng = random.Random(seed)
    out = ["-- Hidden dataset for sql-monthly-revenue (generated; do not edit)."]
    start = datetime(2024, 1, 1, tzinfo=UTC)
    end = datetime(2025, 7, 1, tzinfo=UTC)

    change_dates = []
    out.append("INSERT INTO fx_rates VALUES ('USD', '2019-06-01', 1.0);")
    for cur, base in [("EUR", 10850), ("GBP", 12700), ("CAD", 7350)]:
        day = date(2023, 12, 1)
        rate = base
        while day < date(2025, 8, 1):
            out.append(
                f"INSERT INTO fx_rates VALUES ('{cur}', '{day.isoformat()}', {rate / 10000:.4f});"
            )
            change_dates.append(day)
            day += timedelta(days=rng.randint(5, 19))
            rate = max(5000, rate + rng.randint(-150, 150))

    n_customers = 90
    for cid in range(1, n_customers + 1):
        is_test = int(rng.random() < 0.08)
        out.append(
            f"INSERT INTO customers VALUES ({cid}, 'Customer {cid}', "
            f"'{rng.choice(REGIONS)}', {is_test});"
        )

    def random_instant():
        r = rng.random()
        if r < 0.25:  # near a UTC month boundary
            m = rng.randrange(18)
            y, mo = 2024 + (m // 12), m % 12 + 1
            boundary = datetime(y, mo, 1, tzinfo=UTC)
            if boundary == start:
                boundary = datetime(2024, 2, 1, tzinfo=UTC)
            return boundary + timedelta(minutes=rng.randint(-600, 600))
        if r < 0.45:  # near UTC midnight of an FX rate change
            d = rng.choice([d for d in change_dates if date(2024, 1, 2) < d < date(2025, 6, 28)])
            midnight = datetime(d.year, d.month, d.day, tzinfo=UTC)
            return midnight + timedelta(minutes=rng.randint(-540, 540))
        return start + timedelta(seconds=rng.randrange(int((end - start).total_seconds())))

    line_id = refund_id = 0
    for oid in range(1, 1101):
        placed = random_instant()
        status = rng.choices(["paid", "shipped", "pending", "cancelled"], [6, 10, 1, 2])[0]
        currency = rng.choices(["USD", "EUR", "GBP", "CAD"], [4, 3, 2, 1])[0]
        out.append(
            f"INSERT INTO orders VALUES ({oid}, {rng.randint(1, n_customers)}, "
            f"'{stamp(placed, rng.choice(OFFSETS), rng)}', '{currency}', '{status}');"
        )
        total = 0
        for _ in range(rng.randint(1, 4)):
            line_id += 1
            qty = rng.randint(1, 5)
            price = rng.randint(99, 25000)
            total += qty * price
            out.append(
                f"INSERT INTO order_lines VALUES ({line_id}, {oid}, 'SKU-{rng.randint(100, 999)}', "
                f"{qty}, {price});"
            )
        if rng.random() < (0.5 if status == "cancelled" else 0.28):
            for _ in range(rng.choices([1, 2, 3], [6, 3, 1])[0]):
                refund_id += 1
                if rng.random() < 0.3:  # refund lands near a month boundary
                    when = placed + timedelta(days=rng.randint(0, 45))
                    when = datetime(when.year, when.month, 1, tzinfo=UTC) + timedelta(
                        minutes=rng.randint(-500, 500)
                    )
                    if when < placed:
                        when = placed + timedelta(hours=1)
                else:
                    when = placed + timedelta(hours=rng.randint(1, 24 * 75))
                amount = rng.randint(100, max(101, total // 2))
                reason = rng.choice(["damaged", "late delivery", "customer request", "duplicate"])
                out.append(
                    f"INSERT INTO refunds VALUES ({refund_id}, {oid}, "
                    f"'{stamp(when, rng.choice(OFFSETS), rng)}', {amount}, '{reason}');"
                )
    return "\n".join(out) + "\n"


def tie_free(rows):
    """No exact value sits at (or within 0.002 cent of) a half-cent tie."""
    for _, _, dollars in rows:
        frac = abs(dollars * 100) % 1
        if abs(frac - Decimal("0.5")) < Decimal("0.002"):
            return False
    return True


# --------------------------------------------------------------------------- main


def write(path, text, mode=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    if mode:
        path.chmod(mode)


def main():
    # Visible fixture: reference vs reference SQL.
    fx_db = build_db(SCHEMA, FIXTURE_SQL)
    fx_ref = reference_report(fx_db)
    assert tie_free(fx_ref)
    fx_cents = [(m, r, round_cents(v)) for m, r, v in fx_ref]
    assert sql_matches(fx_db, SOLUTION_SQL, fx_cents), "reference SQL disagrees on fixture"
    assert not sql_matches(fx_db, BUGGY_SQL, fx_cents), "buggy SQL passes the fixture"
    expected_visible = [(m, r, c / 100) for m, r, c in fx_cents]

    # Hidden dataset: first seed (from SEED upward) whose totals have no rounding ties.
    seed = SEED
    while True:
        data = make_hidden_dataset(seed)
        db = build_db(SCHEMA, data)
        ref = reference_report(db)
        if tie_free(ref):
            break
        seed += 1
    cents = [(m, r, round_cents(v)) for m, r, v in ref]
    assert sql_matches(db, SOLUTION_SQL, cents), "reference SQL disagrees on hidden dataset"
    assert not sql_matches(db, BUGGY_SQL, cents)
    assert any(c < 0 for _, _, c in cents), "want a net-negative month"
    # a (month, region) with refunds but no counted order lines
    line_keys = set(
        run_sql(
            db,
            """
        SELECT DISTINCT strftime('%Y-%m', o.ordered_at), c.region FROM orders o
        JOIN customers c ON c.id = o.customer_id
        WHERE o.status <> 'cancelled' AND c.is_test = 0""",
        )[1]
    )
    assert any((m, r) not in line_keys for m, r, _ in cents), "want a refund-only month"

    for name, (old, new) in PARTIAL_FIXES.items():
        assert SOLUTION_SQL.count(old) == 1, name
        variant = SOLUTION_SQL.replace(old, new)
        assert not sql_matches(db, variant, cents), f"partial fix passes hidden: {name}"
        visible = sql_matches(fx_db, variant, fx_cents)
        assert visible or name in VISIBLE_CATCHES, f"partial fix fails visible: {name}"
        print(f"partial fix {name!r}: visible {'pass' if visible else 'FAIL'}, hidden FAIL")

    for d in ("repo", "solution", "hidden_tests"):
        shutil.rmtree(ROOT / d, ignore_errors=True)
    visible_test = VISIBLE_TEST_TEMPLATE.replace(
        "__EXPECTED__", "[\n" + "".join(f"    {t!r},\n" for t in expected_visible) + "]"
    )
    repo = ROOT / "repo"
    write(repo / "README.md", README)
    write(repo / "SPEC.md", SPEC)
    write(repo / "schema.sql", SCHEMA)
    write(repo / "run_report.py", RUN_REPORT, 0o755)
    write(repo / "scripts" / "seed_demo_db.py", SEED_DEMO, 0o755)
    write(repo / "reports" / "monthly_revenue.sql", BUGGY_SQL)
    write(repo / "reports" / "top_customers.sql", TOP_CUSTOMERS_SQL)
    write(repo / "reports" / "refund_reasons.sql", REFUND_REASONS_SQL)
    write(repo / "tests" / "test_monthly_revenue.py", visible_test)
    write(repo / "tests" / "fixture.sql", FIXTURE_SQL)
    write(repo / ".gitignore", "*.db\n__pycache__/\n")
    write(ROOT / "solution" / "reports" / "monthly_revenue.sql", SOLUTION_SQL)
    hidden = ROOT / "hidden_tests"
    write(hidden / "test_monthly_revenue.py", visible_test)
    write(hidden / "fixture.sql", FIXTURE_SQL)
    write(hidden / "test_hidden_dataset.py", HIDDEN_TEST)
    write(hidden / "hidden_schema.sql", SCHEMA)
    write(hidden / "hidden_data.sql", data)
    write(hidden / "hidden_expected.json", json.dumps(cents, indent=0) + "\n")
    write(ROOT / "check.sh", CHECK, 0o755)
    write(ROOT / "task.toml", TASK_TOML)

    # The shipped visible test must fail on the buggy repo and pass with the solution.
    for with_solution, want in ((False, 1), (True, 0)):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            shutil.copytree(repo, ws)
            if with_solution:
                shutil.copytree(ROOT / "solution", ws, dirs_exist_ok=True)
            rc = subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                cwd=ws,
                capture_output=True,
            ).returncode
            assert (rc != 0) == bool(want), (with_solution, rc)
    print(f"seed {seed}: {len(cents)} hidden rows, {len(fx_cents)} visible rows")


if __name__ == "__main__":
    main()
