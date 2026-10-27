-- AOV per country with a 95% confidence interval (normal approximation; n >= 200 paid orders per
-- country in the committed data). Backs the README claim that country AOV gaps are noise.

WITH paid_orders AS (
    SELECT order_id, country, sum(net_revenue) AS net_revenue
    FROM fct_order_lines
    GROUP BY 1, 2
    HAVING sum(net_revenue) > 0
)
SELECT
    country,
    count(*)                                                              AS paid_orders,
    round(avg(net_revenue), 2)                                            AS aov_usd,
    round(1.96 * stddev_samp(net_revenue) / sqrt(count(*)), 2)            AS ci_half_width_usd,
    round(avg(net_revenue) - 1.96 * stddev_samp(net_revenue) / sqrt(count(*)), 2) AS ci_low_usd,
    round(avg(net_revenue) + 1.96 * stddev_samp(net_revenue) / sqrt(count(*)), 2) AS ci_high_usd
FROM paid_orders
GROUP BY 1
ORDER BY aov_usd DESC, country;
