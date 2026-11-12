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
