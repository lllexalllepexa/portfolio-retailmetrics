-- Signup cohorts: how much of the observation window each cohort had, and how many
-- non-cancelled orders its customers placed. Later signups place a similar number of orders in
-- less time, which mechanically inflates their month-1 retention.

WITH window_end AS (
    SELECT max(order_date) AS last_day FROM orders
),
orders_per_customer AS (
    SELECT customer_id, count(*) AS orders
    FROM orders
    WHERE status <> 'cancelled'
    GROUP BY 1
)
SELECT
    strftime(c.signup_date, '%Y-%m')                                      AS signup_month,
    count(*)                                                              AS customers,
    round(avg(date_diff('day', c.signup_date, w.last_day)), 0)            AS avg_days_left,
    round(sum(coalesce(o.orders, 0)) / count(*), 2)                       AS non_cancelled_orders_per_customer
FROM customers AS c
CROSS JOIN window_end AS w
LEFT JOIN orders_per_customer AS o ON o.customer_id = c.customer_id
GROUP BY 1
ORDER BY 1;
