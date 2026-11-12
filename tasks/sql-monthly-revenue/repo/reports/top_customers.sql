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
