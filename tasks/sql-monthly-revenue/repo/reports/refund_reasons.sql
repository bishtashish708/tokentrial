-- Refund count and total (order currency) by reason, for the support dashboard.
SELECT
    COALESCE(r.reason, '(none)') AS reason,
    COUNT(*)                     AS refunds,
    SUM(r.amount_cents)          AS total_cents
FROM refunds r
GROUP BY COALESCE(r.reason, '(none)')
ORDER BY refunds DESC, reason;
