-- Monthly gross merchandise value (GMV) from fulfilled lines (excludes cancelled orders).
-- Net quantity accounts for partial returns on returned orders.

SELECT
    strftime('%Y-%m', o.order_date) AS order_month,
    round(sum((oi.quantity - oi.quantity_returned) * oi.unit_price_paid), 2) AS gmv_usd,
    count(DISTINCT o.order_id) AS order_count
FROM order_items AS oi
JOIN orders AS o ON oi.order_id = o.order_id
WHERE o.status IN ('completed', 'returned')
GROUP BY 1
ORDER BY 1;
