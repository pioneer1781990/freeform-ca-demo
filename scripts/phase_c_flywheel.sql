-- Flywheel substrate tables

CREATE OR REPLACE TABLE `new-project-495419.cymbal_retail._flywheel_glossary` (
  term STRING,
  definition STRING,
  synonyms ARRAY<STRING>,
  linked_table STRING,
  linked_column STRING,
  filter_logic STRING,
  source STRING,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);
-- Start EMPTY. Terms get added during demo as the flywheel recommends them.

CREATE OR REPLACE TABLE `new-project-495419.cymbal_retail._flywheel_verified_queries` (
  id STRING,
  nl_question STRING,
  sql_query STRING,
  tables_used ARRAY<STRING>,
  agent_id STRING,
  created_by STRING,
  usage_count INT64,
  last_validated TIMESTAMP
);

INSERT INTO `new-project-495419.cymbal_retail._flywheel_verified_queries`
  (id, nl_question, sql_query, tables_used, agent_id, created_by, usage_count, last_validated)
VALUES
  ('vq1','What is total revenue by month?',
   'SELECT DATE_TRUNC(created_at, MONTH) AS month, SUM(sale_price) AS revenue FROM `new-project-495419.cymbal_retail.order_items` WHERE status NOT IN (\'Cancelled\',\'Returned\') GROUP BY 1 ORDER BY 1',
   ['order_items'],'cymbal_sales_agent','data_team',0,CURRENT_TIMESTAMP()),
  ('vq2','Top 10 customers by spend',
   'SELECT u.id, u.first_name, u.last_name, SUM(oi.sale_price) AS total_spend FROM `new-project-495419.cymbal_retail.order_items` oi JOIN `new-project-495419.cymbal_retail.users` u ON oi.user_id = u.id WHERE oi.status NOT IN (\'Cancelled\',\'Returned\') GROUP BY 1,2,3 ORDER BY 4 DESC LIMIT 10',
   ['order_items','users'],'cymbal_sales_agent','data_team',0,CURRENT_TIMESTAMP()),
  ('vq3','Revenue by product category',
   'SELECT p.category, SUM(oi.sale_price) AS revenue FROM `new-project-495419.cymbal_retail.order_items` oi JOIN `new-project-495419.cymbal_retail.products` p ON oi.product_id = p.id WHERE oi.status NOT IN (\'Cancelled\',\'Returned\') GROUP BY 1 ORDER BY 2 DESC',
   ['order_items','products'],'cymbal_sales_agent','data_team',0,CURRENT_TIMESTAMP()),
  ('vq4','Return rate by brand',
   'SELECT p.brand, COUNTIF(oi.status=\'Returned\')/COUNT(*) AS return_rate FROM `new-project-495419.cymbal_retail.order_items` oi JOIN `new-project-495419.cymbal_retail.products` p ON oi.product_id = p.id GROUP BY 1 HAVING COUNT(*) > 50 ORDER BY 2 DESC',
   ['order_items','products'],'cymbal_sales_agent','data_team',0,CURRENT_TIMESTAMP()),
  ('vq5','Average order value trend',
   'SELECT DATE_TRUNC(created_at, MONTH) AS month, SUM(sale_price)/COUNT(DISTINCT order_id) AS aov FROM `new-project-495419.cymbal_retail.order_items` WHERE status NOT IN (\'Cancelled\',\'Returned\') GROUP BY 1 ORDER BY 1',
   ['order_items'],'cymbal_sales_agent','data_team',0,CURRENT_TIMESTAMP()),
  ('vq6','What is our CSAT score?',
   'SELECT ROUND(COUNTIF(review_score >= 4) / COUNT(*) * 100, 1) AS csat_pct FROM `new-project-495419.cymbal_retail.customer_reviews`',
   ['customer_reviews'],'cymbal_cx_agent','data_team',0,CURRENT_TIMESTAMP()),
  ('vq7','Late delivery rate by month',
   'SELECT DATE_TRUNC(order_purchase_timestamp, MONTH) AS month, COUNTIF(order_delivered_customer_date > order_estimated_delivery_date)/COUNTIF(order_delivered_customer_date IS NOT NULL) AS late_rate FROM `new-project-495419.cymbal_retail.marketplace_orders` WHERE order_status = \'delivered\' GROUP BY 1 ORDER BY 1',
   ['marketplace_orders'],'cymbal_cx_agent','data_team',0,CURRENT_TIMESTAMP()),
  ('vq8','Average review score by payment type',
   'SELECT cp.payment_type, AVG(CAST(cr.review_score AS INT64)) AS avg_score FROM `new-project-495419.cymbal_retail.customer_payments` cp JOIN `new-project-495419.cymbal_retail.customer_reviews` cr ON cp.order_id = cr.order_id GROUP BY 1 ORDER BY 2',
   ['customer_payments','customer_reviews'],'cymbal_cx_agent','data_team',0,CURRENT_TIMESTAMP());

CREATE OR REPLACE TABLE `new-project-495419.cymbal_retail._flywheel_agents` (
  agent_id STRING,
  name STRING,
  description STRING,
  tables_in_scope ARRAY<STRING>,
  glossary_terms ARRAY<STRING>,
  system_instruction STRING,
  status STRING,
  ca_api_synced BOOL,
  question_count INT64,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);
-- EMPTY at start. Agents created live during demo.

CREATE OR REPLACE TABLE `new-project-495419.cymbal_retail._flywheel_query_log` (
  query_id STRING,
  user_id STRING,
  question_text STRING,
  generated_sql STRING,
  tables_referenced ARRAY<STRING>,
  path_taken STRING,
  agent_used STRING,
  confidence_score FLOAT64,
  success BOOL,
  error_message STRING,
  thumbs STRING,
  correction STRING,
  created_at TIMESTAMP
);

CREATE OR REPLACE TABLE `new-project-495419.cymbal_retail._flywheel_memory` (
  id STRING,
  user_id STRING,
  memory_type STRING,
  key STRING,
  value STRING,
  source_question STRING,
  promoted_to_semantic BOOL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

INSERT INTO `new-project-495419.cymbal_retail._flywheel_memory`
  (id, user_id, memory_type, key, value, source_question, promoted_to_semantic) VALUES
  ('mem_001','user_alice','user','active_customer_definition','Customer with order in last 60 days, not 90','How many active customers do we have?',FALSE),
  ('mem_002','user_bob',  'user','active_customer_definition','Active means purchased within 60 days',      'Show me active customer count',         FALSE),
  ('mem_003','user_carol','user','active_customer_definition','We define active as 60-day purchase window', 'What is our active customer base?',     FALSE),
  ('mem_004','user_dave', 'user','stockout_definition',       'Stockout = qty_on_hand <= safety_stock, not just zero','Which products are at stockout risk?',FALSE),
  ('mem_005','user_eve',  'user','days_of_supply',            'DOS = qty_on_hand / avg_daily_demand from last 30 days','What is our days of supply for top sellers?',FALSE);

CREATE OR REPLACE TABLE `new-project-495419.cymbal_retail._flywheel_prep_recs` (
  id STRING,
  rec_type STRING,
  target_table STRING,
  target_column STRING,
  detail STRING,
  question_frequency INT64,
  priority_score FLOAT64,
  status STRING,
  applied_action STRING,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);
