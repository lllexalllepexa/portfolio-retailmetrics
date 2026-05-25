-- Country mix: customers, orders, average order value (AOV).

WITH line_revenue AS (
    SELECT
        o.order_id,
        c.country,
        sum((oi.quantity - oi.quantity_returned) * oi.unit_price_paid) AS revenue
    FROM order_items AS oi
    JOIN orders AS o ON oi.order_id = o.order_id
    JOIN customers AS c ON o.customer_id = c.customer_id
    WHERE o.status IN ('completed', 'returned')
    GROUP BY 1, 2
)
SELECT
    country,
    count(DISTINCT order_id) AS orders,
    round(sum(revenue), 2) AS gmv_usd,
    round(sum(revenue) / nullif(count(DISTINCT order_id), 0), 2) AS aov_usd
FROM line_revenue
GROUP BY 1
ORDER BY gmv_usd DESC;
