-- First-purchase cohort retention, months 0-3.
--   cohort_month     = calendar month of a customer's first qualifying order
--   retention_rate_n = share of the cohort with >= 1 qualifying order in month (cohort_month + n)
-- Month 0 is 100% by definition. The spine keeps zero-activity cells as 0.0; cells that fall
-- after the last month in the data are right-censored and omitted (not reported as 0).
-- retention_ci_low / _high: 95% Wilson score interval, so small cohorts show their uncertainty.

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
),
cells AS (
    SELECT
        s.cohort_month,
        s.cohort_customers,
        s.month_offset,
        count(a.customer_id)                        AS active_customers,
        count(a.customer_id) / s.cohort_customers   AS p,
        1.96                                        AS z
    FROM spine AS s
    LEFT JOIN activity AS a
           ON a.cohort_month = s.cohort_month
          AND a.month_offset = s.month_offset
    GROUP BY s.cohort_month, s.cohort_customers, s.month_offset
)
SELECT
    strftime(cohort_month, '%Y-%m')                                     AS cohort_month,
    cohort_customers,
    CAST(month_offset AS INTEGER)                                       AS month_offset,
    active_customers,
    round(p, 3)                                                         AS retention_rate,
    round(
        (p + z * z / (2 * cohort_customers)
           - z * sqrt(p * (1 - p) / cohort_customers + z * z / (4 * cohort_customers * cohort_customers)))
        / (1 + z * z / cohort_customers), 3)                            AS retention_ci_low,
    round(
        (p + z * z / (2 * cohort_customers)
           + z * sqrt(p * (1 - p) / cohort_customers + z * z / (4 * cohort_customers * cohort_customers)))
        / (1 + z * z / cohort_customers), 3)                            AS retention_ci_high
FROM cells
ORDER BY 1, 3;
