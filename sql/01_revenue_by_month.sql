-- Monthly gross and net revenue for qualifying (completed + returned) orders.
-- order_count includes fully returned orders, which contribute 0 net revenue.

SELECT
    strftime(order_date, '%Y-%m')                                       AS order_month,
    round(sum(gross_revenue), 2)                                        AS gross_revenue_usd,
    round(sum(net_revenue), 2)                                          AS net_revenue_usd,
    round(sum(returned_revenue) / nullif(sum(gross_revenue), 0), 4)     AS return_rate,
    count(DISTINCT order_id)                                            AS order_count
FROM fct_order_lines
GROUP BY 1
ORDER BY 1;
