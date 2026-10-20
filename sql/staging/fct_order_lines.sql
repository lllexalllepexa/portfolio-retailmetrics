-- Staging fact: one row per order line on a qualifying order (completed or returned).
-- Every revenue measure used by the marts is defined here, once.
--   gross_revenue    = units ordered  x price paid (after discount, before returns)
--   returned_revenue = units returned x price paid
--   net_revenue      = gross_revenue - returned_revenue
--   discount_amount  = units ordered  x (list price - price paid)

CREATE OR REPLACE VIEW fct_order_lines AS
SELECT
    oi.order_line_id,
    oi.order_id,
    o.customer_id,
    c.country,
    oi.product_id,
    p.name                                                     AS product_name,
    p.category,
    o.order_date,
    o.status,
    oi.quantity,
    oi.quantity_returned,
    oi.quantity - oi.quantity_returned                         AS quantity_net,
    oi.quantity * oi.unit_price_paid                           AS gross_revenue,
    oi.quantity_returned * oi.unit_price_paid                  AS returned_revenue,
    (oi.quantity - oi.quantity_returned) * oi.unit_price_paid  AS net_revenue,
    oi.quantity * (p.list_price - oi.unit_price_paid)          AS discount_amount
FROM order_items AS oi
JOIN orders    AS o ON oi.order_id   = o.order_id
JOIN customers AS c ON o.customer_id = c.customer_id
JOIN products  AS p ON oi.product_id = p.product_id
WHERE o.status IN ('completed', 'returned');
