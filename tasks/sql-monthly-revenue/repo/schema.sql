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
