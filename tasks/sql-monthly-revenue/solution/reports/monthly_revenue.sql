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
