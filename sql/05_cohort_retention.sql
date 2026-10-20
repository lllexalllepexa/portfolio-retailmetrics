-- First-purchase cohort retention, months 0-3.
--   cohort_month     = calendar month of a customer's first qualifying order
--   retention_rate_n = share of the cohort with >= 1 qualifying order in month (cohort_month + n)
-- Month 0 is 100% by definition. The spine keeps zero-activity cells as 0.0; cells that fall
-- after the last month in the data are right-censored and omitted (not reported as 0).

WITH customer_months AS (
    SELECT DISTINCT
        customer_id,
        date_trunc('month', order_date) AS activity_month
    FROM fct_order_lines
),
first_purchase AS (
    SELECT customer_id, min(activity_month) AS cohort_month
    FROM customer_months
    GROUP BY 1
),
activity AS (
    SELECT
        f.customer_id,
        f.cohort_month,
        date_diff('month', f.cohort_month, m.activity_month) AS month_offset
    FROM first_purchase AS f
    JOIN customer_months AS m ON m.customer_id = f.customer_id
),
cohort_sizes AS (
    SELECT cohort_month, count(*) AS cohort_customers
    FROM first_purchase
    GROUP BY 1
),
spine AS (
    SELECT cs.cohort_month, cs.cohort_customers, o.month_offset
    FROM cohort_sizes AS cs
    CROSS JOIN range(0, 4) AS o(month_offset)
    WHERE cs.cohort_month + to_months(CAST(o.month_offset AS INTEGER))
          <= (SELECT max(activity_month) FROM customer_months)
)
SELECT
    strftime(s.cohort_month, '%Y-%m')                                   AS cohort_month,
    s.cohort_customers,
    CAST(s.month_offset AS INTEGER)                                     AS month_offset,
    count(a.customer_id)                                                AS active_customers,
    round(count(a.customer_id) / s.cohort_customers, 3)                 AS retention_rate
FROM spine AS s
LEFT JOIN activity AS a
       ON a.cohort_month = s.cohort_month
      AND a.month_offset = s.month_offset
GROUP BY s.cohort_month, s.cohort_customers, s.month_offset
ORDER BY 1, 3;
