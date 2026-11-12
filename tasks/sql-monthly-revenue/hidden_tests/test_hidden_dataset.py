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
