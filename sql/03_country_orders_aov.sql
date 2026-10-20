-- Country mix: order volume, revenue and average order value (AOV).
--   orders      = qualifying orders (completed + returned, incl. fully returned)
--   paid_orders = orders that kept > 0 net revenue after returns
--   aov_usd     = net revenue / paid_orders, so fully refunded orders do not dilute AOV

WITH order_revenue AS (
    SELECT
        order_id,
        country,
        sum(gross_revenue) AS gross_revenue,
        sum(net_revenue)   AS net_revenue
    FROM fct_order_lines
    GROUP BY 1, 2
)
SELECT
    country,
    count(*)                                                            AS orders,
    count(*) FILTER (WHERE net_revenue > 0)                             AS paid_orders,
    round(sum(gross_revenue), 2)                                        AS gross_revenue_usd,
    round(sum(net_revenue), 2)                                          AS net_revenue_usd,
    round(sum(net_revenue) / nullif(count(*) FILTER (WHERE net_revenue > 0), 0), 2) AS aov_usd
FROM order_revenue
GROUP BY 1
ORDER BY net_revenue_usd DESC, country;
