-- Signup-based cohorts: denominator = customers who signed up in cohort_month AND have ≥1 qualifying order.
-- Retention at offset n = share of that cohort with ≥1 qualifying order in calendar month (signup_month + n).

WITH signup AS (
    SELECT
        customer_id,
        date_trunc('month', cast(signup_date AS DATE)) AS cohort_month
    FROM customers
),
eligible AS (
    SELECT DISTINCT s.customer_id, s.cohort_month
    FROM signup AS s
    WHERE EXISTS (
        SELECT 1
        FROM orders AS o
        WHERE o.customer_id = s.customer_id
          AND o.status IN ('completed', 'returned')
    )
),
activity AS (
    SELECT DISTINCT
        e.customer_id,
        e.cohort_month,
        date_trunc('month', cast(o.order_date AS DATE)) AS activity_month
    FROM eligible AS e
    JOIN orders AS o ON e.customer_id = o.customer_id
    WHERE o.status IN ('completed', 'returned')
),
with_offset AS (
    SELECT
        customer_id,
        strftime('%Y-%m', cohort_month) AS cohort_month,
        date_diff('month', cohort_month, activity_month) AS month_offset
    FROM activity
),
cohort_sizes AS (
    SELECT
        strftime('%Y-%m', cohort_month) AS cohort_month,
        count(DISTINCT customer_id) AS cohort_customers
    FROM eligible
    GROUP BY 1
)
SELECT
    w.cohort_month,
    cs.cohort_customers,
    w.month_offset,
    round(count(DISTINCT w.customer_id) * 1.0 / cs.cohort_customers, 3) AS retention_rate
FROM with_offset AS w
JOIN cohort_sizes AS cs ON w.cohort_month = cs.cohort_month
WHERE w.month_offset BETWEEN 0 AND 3
GROUP BY 1, 2, 3
ORDER BY 1, 3;
