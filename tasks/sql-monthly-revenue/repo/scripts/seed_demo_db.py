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
