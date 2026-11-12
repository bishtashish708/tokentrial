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
