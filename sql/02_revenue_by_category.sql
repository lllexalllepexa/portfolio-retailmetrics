-- GMV by product category (completed + returned with net qty).

SELECT
    p.category,
    round(sum((oi.quantity - oi.quantity_returned) * oi.unit_price_paid), 2) AS gmv_usd,
    sum(oi.quantity - oi.quantity_returned) AS units_sold_net
FROM order_items AS oi
JOIN orders AS o ON oi.order_id = o.order_id
JOIN products AS p ON oi.product_id = p.product_id
WHERE o.status IN ('completed', 'returned')
GROUP BY 1
ORDER BY gmv_usd DESC;
