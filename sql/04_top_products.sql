-- Top 15 products by net revenue.

SELECT
    p.product_id,
    p.name,
    p.category,
    round(sum((oi.quantity - oi.quantity_returned) * oi.unit_price_paid), 2) AS gmv_usd
FROM order_items AS oi
JOIN orders AS o ON oi.order_id = o.order_id
JOIN products AS p ON oi.product_id = p.product_id
WHERE o.status IN ('completed', 'returned')
GROUP BY 1, 2, 3
ORDER BY gmv_usd DESC
LIMIT 15;
