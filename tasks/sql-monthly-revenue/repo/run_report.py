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
        out.write("  ".join(v.ljust(w) for v, w in zip(row, widths)).rstrip() + "\n")
        if n == 0:
            out.write("  ".join("-" * w for w in widths) + "\n")


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
