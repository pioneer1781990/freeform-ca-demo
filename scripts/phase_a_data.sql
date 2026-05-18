-- ===========================================================
-- PHASE A: Tables that don't depend on Olist
-- Run with: bq query --use_legacy_sql=false --project_id=new-project-495419 --location=us-central1 < phase_a_data.sql
-- ===========================================================

-- --- 3.1 SALES & REVENUE (thelook) -------------------------
CREATE OR REPLACE TABLE `new-project-495419.cymbal_retail.orders` AS
SELECT * FROM `bigquery-public-data.thelook_ecommerce.orders`;

CREATE OR REPLACE TABLE `new-project-495419.cymbal_retail.order_items` AS
SELECT * FROM `bigquery-public-data.thelook_ecommerce.order_items`;

CREATE OR REPLACE TABLE `new-project-495419.cymbal_retail.products` AS
SELECT * FROM `bigquery-public-data.thelook_ecommerce.products`;

CREATE OR REPLACE TABLE `new-project-495419.cymbal_retail.users` AS
SELECT * FROM `bigquery-public-data.thelook_ecommerce.users`;

-- Descriptions
ALTER TABLE `new-project-495419.cymbal_retail.orders`
SET OPTIONS (description = 'Cymbal Retail direct ecommerce orders. Status values: Shipped, Complete, Processing, Cancelled, Returned. Each order links to a user via user_id.');

ALTER TABLE `new-project-495419.cymbal_retail.order_items`
SET OPTIONS (description = 'Line items for each order. sale_price is the actual price paid (use this for revenue). status tracks item-level fulfillment. user_id links directly to users table.');

ALTER TABLE `new-project-495419.cymbal_retail.products`
SET OPTIONS (description = 'Product catalog. cost = wholesale cost to Cymbal. retail_price = suggested retail. department is Men or Women. category and brand are the primary product dimensions.');

ALTER TABLE `new-project-495419.cymbal_retail.users`
SET OPTIONS (description = 'Cymbal Retail customer master record. Includes demographics, geography, and acquisition channel (traffic_source).');

ALTER TABLE `new-project-495419.cymbal_retail.order_items`
ALTER COLUMN sale_price SET OPTIONS (description = 'Actual price paid by customer for this item. USE THIS FOR REVENUE CALCULATIONS, not products.retail_price.');

ALTER TABLE `new-project-495419.cymbal_retail.order_items`
ALTER COLUMN status SET OPTIONS (description = 'Item fulfillment status: Shipped, Complete, Processing, Cancelled, Returned. Exclude Cancelled and Returned from revenue metrics.');

ALTER TABLE `new-project-495419.cymbal_retail.products`
ALTER COLUMN retail_price SET OPTIONS (description = 'Suggested retail price (MSRP). NOT the actual sale price. For revenue, use order_items.sale_price.');

ALTER TABLE `new-project-495419.cymbal_retail.products`
ALTER COLUMN cost SET OPTIONS (description = 'Wholesale cost to Cymbal Retail. Margin = order_items.sale_price - products.cost.');

-- --- 3.3 SUPPLY CHAIN (thelook + synthetic, NO descriptions) ---
CREATE OR REPLACE TABLE `new-project-495419.cymbal_retail.distribution_centers` AS
SELECT * FROM `bigquery-public-data.thelook_ecommerce.distribution_centers`;

CREATE OR REPLACE TABLE `new-project-495419.cymbal_retail.inventory_items` AS
SELECT * FROM `bigquery-public-data.thelook_ecommerce.inventory_items`;

-- Synthetic: inventory_snapshots (deliberately bare)
CREATE OR REPLACE TABLE `new-project-495419.cymbal_retail.inventory_snapshots` AS
SELECT
  date,
  product_id,
  dc_id,
  CAST(FLOOR(RAND() * 500) AS INT64) AS qty_on_hand,
  CAST(FLOOR(RAND() * 50) AS INT64) AS qty_reserved,
  CAST(FLOOR(RAND() * 100 + 20) AS INT64) AS reorder_point,
  ROUND(RAND() * 60 + 5, 1) AS days_of_supply,
  ROUND(RAND() * 50 + 10, 2) AS avg_daily_demand
FROM
  UNNEST(GENERATE_DATE_ARRAY('2026-01-01', '2026-05-17', INTERVAL 1 WEEK)) AS date,
  (SELECT DISTINCT id AS product_id FROM `new-project-495419.cymbal_retail.products` LIMIT 50) AS products,
  (SELECT DISTINCT id AS dc_id FROM `new-project-495419.cymbal_retail.distribution_centers`) AS dcs;

-- Synthetic: supplier_catalog
CREATE OR REPLACE TABLE `new-project-495419.cymbal_retail.supplier_catalog` AS
SELECT
  CONCAT('SUP-', CAST(ROW_NUMBER() OVER() AS STRING)) AS supplier_id,
  category,
  CAST(FLOOR(RAND() * 21 + 7) AS INT64) AS lead_time_days,
  CAST(FLOOR(RAND() * 100 + 10) AS INT64) AS min_order_qty,
  ROUND(RAND() * 80 + 5, 2) AS unit_cost,
  ROUND(RAND() * 0.5 + 0.5, 2) AS reliability_score
FROM (SELECT DISTINCT category FROM `new-project-495419.cymbal_retail.products` WHERE category IS NOT NULL);

-- --- 3.4 VOICE OF CUSTOMER (synthetic, NO descriptions) -------
CREATE OR REPLACE TABLE `new-project-495419.cymbal_retail.support_tickets` AS
SELECT * FROM UNNEST([
  STRUCT('TKT001' AS ticket_id, 1001 AS customer_id, 10001 AS order_id, 'email' AS channel, 'Late delivery' AS subject, 'high' AS priority, 'open' AS status, TIMESTAMP '2026-05-10 14:30:00' AS created_at),
  STRUCT('TKT002', 1002, 10002, 'chat', 'Wrong size received', 'medium', 'resolved', TIMESTAMP '2026-05-08 09:15:00'),
  STRUCT('TKT003', 1003, 10003, 'phone', 'Damaged product', 'high', 'escalated', TIMESTAMP '2026-05-12 11:00:00'),
  STRUCT('TKT004', 1004, 10004, 'email', 'Refund not processed', 'high', 'open', TIMESTAMP '2026-05-14 16:45:00'),
  STRUCT('TKT005', 1005, 10005, 'chat', 'Product not as described', 'medium', 'open', TIMESTAMP '2026-05-15 10:20:00'),
  STRUCT('TKT006', 1006, 10006, 'email', 'Missing item in order', 'high', 'open', TIMESTAMP '2026-05-11 08:00:00'),
  STRUCT('TKT007', 1007, 10007, 'phone', 'Great experience, thank you', 'low', 'resolved', TIMESTAMP '2026-05-09 13:30:00'),
  STRUCT('TKT008', 1008, 10008, 'email', 'Shipping delay inquiry', 'medium', 'open', TIMESTAMP '2026-05-16 09:00:00')
]);

CREATE OR REPLACE TABLE `new-project-495419.cymbal_retail.return_claims` (
  claim_id STRING,
  order_id INT64,
  product_id INT64,
  reason_code STRING,
  customer_description STRING,
  has_photo_evidence BOOL,
  created_at TIMESTAMP
);

INSERT INTO `new-project-495419.cymbal_retail.return_claims` VALUES
  ('CLM001', 10003, 201, 'damaged', 'Box was crushed and product cracked', TRUE, TIMESTAMP '2026-05-12 12:00:00'),
  ('CLM002', 10005, 305, 'not_as_described', 'Color completely different from listing', TRUE, TIMESTAMP '2026-05-15 11:00:00'),
  ('CLM003', 10002, 150, 'wrong_item', 'Ordered medium, received XL', FALSE, TIMESTAMP '2026-05-08 10:00:00');

-- --- 3.0 DEV/STAGING tables (agent_ready: false) ---
CREATE OR REPLACE TABLE `new-project-495419.cymbal_retail.orders_staging` AS
SELECT * FROM `new-project-495419.cymbal_retail.orders` WHERE RAND() < 0.1;

CREATE OR REPLACE TABLE `new-project-495419.cymbal_retail.products_dev` AS
SELECT id, name, brand FROM `new-project-495419.cymbal_retail.products` WHERE RAND() < 0.05;

CREATE OR REPLACE TABLE `new-project-495419.cymbal_retail.user_events_raw` (
  user_id INT64, event_time TIMESTAMP, event_type STRING, page STRING
);

CREATE OR REPLACE TABLE `new-project-495419.cymbal_retail.tmp_analysis_20260510` (placeholder INT64);
