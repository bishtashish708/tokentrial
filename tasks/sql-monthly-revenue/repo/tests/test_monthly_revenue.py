"""Tests for reports/monthly_revenue.sql on a small fixture (see SPEC.md)."""

import sqlite3
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

EXPECTED = [
    ('2024-01', 'EMEA', 220.0),
    ('2024-01', 'NA', 79.99),
    ('2024-02', 'EMEA', 50.77),
    ('2024-02', 'NA', 15.0),
    ('2024-03', 'EMEA', 14.0),
]


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
