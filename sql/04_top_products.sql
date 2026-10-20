-- Top 15 products by net revenue (ties broken by product_id for deterministic output).

SELECT
    product_id,
    product_name,
    category,
    round(sum(gross_revenue), 2)                                        AS gross_revenue_usd,
    round(sum(net_revenue), 2)                                          AS net_revenue_usd,
    round(sum(returned_revenue) / nullif(sum(gross_revenue), 0), 4)     AS return_rate,
    CAST(sum(quantity_net) AS BIGINT)                                   AS units_sold_net
FROM fct_order_lines
GROUP BY 1, 2, 3
ORDER BY net_revenue_usd DESC, product_id
LIMIT 15;
