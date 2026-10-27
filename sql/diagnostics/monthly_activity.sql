-- Growth decomposition: signups, active buyers, orders and net revenue per order by month.
-- Shows that monthly growth is order volume from a growing customer base, not order value.

WITH months AS (
    SELECT DISTINCT date_trunc('month', order_date) AS month FROM fct_order_lines
),
signups AS (
    SELECT date_trunc('month', signup_date) AS month, count(*) AS new_signups
    FROM customers
    GROUP BY 1
),
activity AS (
    SELECT
        date_trunc('month', order_date)  AS month,
        count(DISTINCT customer_id)      AS active_buyers,
        count(DISTINCT order_id)         AS orders,
        sum(net_revenue)                 AS net_revenue
    FROM fct_order_lines
    GROUP BY 1
)
SELECT
    strftime(m.month, '%Y-%m')                                            AS month,
    coalesce(s.new_signups, 0)                                            AS new_signups,
    CAST(sum(coalesce(s.new_signups, 0)) OVER (ORDER BY m.month) AS BIGINT) AS cumulative_signups,
    a.active_buyers,
    a.orders,
    round(a.net_revenue / a.orders, 2)                                    AS net_revenue_per_order_usd
FROM months AS m
LEFT JOIN signups  AS s ON s.month = m.month
LEFT JOIN activity AS a ON a.month = m.month
ORDER BY 1;
