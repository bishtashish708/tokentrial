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
