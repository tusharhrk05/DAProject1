-- query: business_kpis
SELECT
    COUNT(*) AS bill_count,
    ROUND(COALESCE(SUM(total), 0), 2) AS recorded_sales,
    ROUND(COALESCE(SUM(paid_amount), 0), 2) AS payments_collected,
    ROUND(COALESCE(SUM(balance_due), 0), 2) AS customer_balance_due,
    ROUND(COALESCE(AVG(total), 0), 2) AS average_bill_value
FROM bills;

-- query: monthly_sales
SELECT
    substr(bill_date, 1, 7) AS month,
    COUNT(*) AS bill_count,
    ROUND(SUM(total), 2) AS sales,
    ROUND(SUM(paid_amount), 2) AS collected,
    ROUND(SUM(balance_due), 2) AS balance_due
FROM bills
WHERE bill_date IS NOT NULL AND bill_date <> ''
GROUP BY substr(bill_date, 1, 7)
ORDER BY month;

-- query: category_sales
SELECT
    COALESCE(NULLIF(category, ''), 'Other') AS category,
    SUM(quantity) AS units_sold,
    ROUND(SUM(line_total), 2) AS sales
FROM bill_items
GROUP BY COALESCE(NULLIF(category, ''), 'Other')
ORDER BY sales DESC, category;

-- query: top_products
SELECT
    product_name,
    COALESCE(NULLIF(category, ''), 'Other') AS category,
    SUM(quantity) AS units_sold,
    COUNT(DISTINCT bill_id) AS bills,
    ROUND(SUM(line_total), 2) AS sales
FROM bill_items
GROUP BY product_id, product_name, COALESCE(NULLIF(category, ''), 'Other')
ORDER BY units_sold DESC, sales DESC
LIMIT 20;

-- query: customer_lifetime
SELECT
    c.customer_id,
    c.name AS customer,
    c.company_name,
    c.phone,
    COUNT(b.bill_id) AS visits,
    ROUND(COALESCE(SUM(b.total), 0), 2) AS lifetime_spend,
    ROUND(COALESCE(SUM(b.paid_amount), 0), 2) AS lifetime_paid,
    ROUND(COALESCE(SUM(b.balance_due), 0), 2) AS lifetime_pending
FROM customers c
LEFT JOIN bills b ON b.customer_id = c.customer_id
GROUP BY c.customer_id, c.name, c.company_name, c.phone
ORDER BY lifetime_spend DESC, customer;

-- query: inventory_health
SELECT
    product_id,
    name AS product,
    category,
    stock,
    reorder_level,
    CASE WHEN stock = 0 THEN 'Out of stock'
         WHEN stock <= reorder_level THEN 'Reorder'
         ELSE 'Healthy' END AS stock_status,
    ROUND(stock * purchase_rate, 2) AS stock_cost_value,
    purchase_rate_estimated
FROM products
ORDER BY CASE WHEN stock = 0 THEN 0 WHEN stock <= reorder_level THEN 1 ELSE 2 END,
         stock ASC, name;

-- query: supplier_summary
SELECT
    supplier,
    COUNT(*) AS purchase_count,
    ROUND(SUM(total), 2) AS purchase_total,
    ROUND(SUM(paid_amount), 2) AS paid,
    ROUND(SUM(balance_due), 2) AS payable_due
FROM purchases
GROUP BY supplier
ORDER BY purchase_total DESC, supplier;

-- query: payment_methods
SELECT
    COALESCE(NULLIF(payment_method, ''), 'Unspecified') AS payment_method,
    COUNT(*) AS payment_count,
    ROUND(SUM(amount), 2) AS amount_collected
FROM bill_payments
GROUP BY COALESCE(NULLIF(payment_method, ''), 'Unspecified')
ORDER BY amount_collected DESC, payment_method;
