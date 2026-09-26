-- SQLite queries against outputs/retail.db
-- Reconcile the headline revenue and valid invoice count.
SELECT ROUND(SUM(revenue), 2) AS merchandise_revenue_gbp,
       COUNT(DISTINCT InvoiceNo) AS valid_invoices
FROM valid_sales;

-- Monthly revenue. December 2011 is partial and omitted.
SELECT month, ROUND(SUM(revenue), 2) AS revenue_gbp
FROM valid_sales
WHERE month BETWEEN '2011-01' AND '2011-11'
GROUP BY month ORDER BY month;

-- Customer value segments based on observed-period spend; unknown IDs excluded.
WITH customer_value AS (
  SELECT CustomerID, ROUND(SUM(revenue), 2) AS sales_gbp,
         COUNT(DISTINCT InvoiceNo) AS invoices
  FROM valid_sales WHERE CustomerID IS NOT NULL
  GROUP BY CustomerID
)
SELECT CASE WHEN invoices >= 2 THEN 'repeat' ELSE 'single invoice' END AS segment,
       COUNT(*) AS customers, ROUND(SUM(sales_gbp), 2) AS sales_gbp
FROM customer_value GROUP BY segment;

-- Cohorts with complete month-1 observation window.
SELECT * FROM cohort_month_1 ORDER BY cohort;
