"""Seed _flywheel_query_log with 100 synthetic historical queries, deliberately
clustered so the orchestrator's signal-harvest can recommend agents + prep actions."""
import warnings; warnings.filterwarnings("ignore")
import uuid, random
from datetime import datetime, timedelta, timezone
from google.cloud import bigquery

PROJECT = "new-project-495419"
DS      = "cymbal_retail"
bq = bigquery.Client(project=PROJECT)

USERS = ["user_alice","user_bob","user_carol","user_dave","user_eve","user_frank","user_grace"]
NOW   = datetime.now(timezone.utc)

# (question, sql, tables, path, agent, conf, success, err, thumbs, correction)
CLUSTERS = [
  # --- Cluster 1: Sales / revenue (30) -- all hit orders/order_items/products ---
  *[("What was revenue last month?",
     "SELECT SUM(sale_price) FROM `{ds}.order_items` WHERE created_at >= DATE_TRUNC(CURRENT_DATE(), MONTH) - INTERVAL 1 MONTH AND status NOT IN ('Cancelled','Returned')",
     ["order_items"], "freelance", None, 0.62, True, None, None, None) for _ in range(8)],
  *[("Top 10 selling products this quarter",
     "SELECT p.name, SUM(oi.sale_price) AS rev FROM `{ds}.order_items` oi JOIN `{ds}.products` p ON oi.product_id=p.id WHERE oi.created_at >= DATE_TRUNC(CURRENT_DATE(),QUARTER) GROUP BY 1 ORDER BY 2 DESC LIMIT 10",
     ["order_items","products"], "freelance", None, 0.65, True, None, None, None) for _ in range(7)],
  *[("Revenue by department",
     "SELECT p.department, SUM(oi.sale_price) AS rev FROM `{ds}.order_items` oi JOIN `{ds}.products` p ON oi.product_id=p.id GROUP BY 1",
     ["order_items","products"], "freelance", None, 0.7, True, None, None, None) for _ in range(6)],
  *[("Active customers count",
     None, ["users","order_items"], "refuse", None, 0.0, False, "Term 'active customer' not defined in glossary", None, None) for _ in range(5)],
  *[("Average order value by month",
     "SELECT DATE_TRUNC(created_at, MONTH) m, SUM(sale_price)/COUNT(DISTINCT order_id) FROM `{ds}.order_items` GROUP BY 1",
     ["order_items"], "freelance", None, 0.6, True, None, "up", None) for _ in range(4)],

  # --- Cluster 2: CX / reviews / late delivery (25) ---
  *[("Average review score",
     "SELECT AVG(CAST(review_score AS INT64)) FROM `{ds}.customer_reviews`",
     ["customer_reviews"], "freelance", None, 0.7, True, None, None, None) for _ in range(7)],
  *[("Late delivery rate",
     "SELECT COUNTIF(order_delivered_customer_date>order_estimated_delivery_date)/COUNT(*) FROM `{ds}.marketplace_orders`",
     ["marketplace_orders"], "freelance", None, 0.55, True, None, None, None) for _ in range(6)],
  *[("CSAT this month",
     None, ["customer_reviews"], "refuse", None, 0.0, False, "Term 'CSAT' not defined in glossary", None, None) for _ in range(5)],
  *[("Reviews mentioning 'damaged'",
     "SELECT review_id, review_comment_message FROM `{ds}.customer_reviews` WHERE LOWER(review_comment_message) LIKE '%danific%' OR LOWER(review_comment_message) LIKE '%quebrad%'",
     ["customer_reviews"], "freelance", None, 0.5, True, None, "down", "Reviews are in Portuguese — must search for 'danificado','quebrado' not English words") for _ in range(4)],
  *[("Top sellers by review score",
     "SELECT ms.seller_id, AVG(CAST(cr.review_score AS INT64)) FROM `{ds}.marketplace_sellers` ms JOIN `{ds}.marketplace_orders` mo ON 1=1 JOIN `{ds}.customer_reviews` cr ON mo.order_id=cr.order_id GROUP BY 1 ORDER BY 2 DESC",
     ["marketplace_sellers","marketplace_orders","customer_reviews"], "freelance", None, 0.4, False, "Cartesian join in marketplace_sellers — missing seller-order link", None, None) for _ in range(3)],

  # --- Cluster 3: Supply chain (20) -- bare domain, lots of hedging/refusal ---
  *[("Which products are at stockout risk?",
     None, ["inventory_snapshots"], "refuse", None, 0.0, False, "Term 'stockout' not defined in glossary; no description on inventory_snapshots", None, None) for _ in range(6)],
  *[("Days of supply for top sellers",
     None, ["inventory_snapshots","order_items"], "refuse", None, 0.0, False, "Term 'days of supply' not defined; columns lack descriptions", None, None) for _ in range(5)],
  *[("Inventory by distribution center",
     "SELECT dc_id, SUM(qty_on_hand) FROM `{ds}.inventory_snapshots` WHERE date = (SELECT MAX(date) FROM `{ds}.inventory_snapshots`) GROUP BY 1",
     ["inventory_snapshots"], "freelance", None, 0.5, True, None, None, None) for _ in range(5)],
  *[("Supplier lead times",
     "SELECT category, AVG(lead_time_days) FROM `{ds}.supplier_catalog` GROUP BY 1",
     ["supplier_catalog"], "freelance", None, 0.6, True, None, None, None) for _ in range(4)],

  # --- Cluster 4: VoC / support / unstructured (15) ---
  *[("Open high-priority support tickets",
     "SELECT * FROM `{ds}.support_tickets` WHERE priority='high' AND status='open'",
     ["support_tickets"], "freelance", None, 0.7, True, None, None, None) for _ in range(5)],
  *[("Return claims with photo evidence",
     "SELECT * FROM `{ds}.return_claims` WHERE has_photo_evidence",
     ["return_claims"], "freelance", None, 0.7, True, None, None, None) for _ in range(4)],
  *[("Summarize all support emails",
     None, ["support_ticket_docs"], "refuse", None, 0.0, False, "Unstructured content; needs ObjectRef + AI.GENERATE on doc_ref", None, None) for _ in range(3)],
  *[("Tickets escalated this week",
     "SELECT * FROM `{ds}.support_tickets` WHERE status='escalated' AND created_at>=TIMESTAMP_SUB(CURRENT_TIMESTAMP(),INTERVAL 7 DAY)",
     ["support_tickets"], "freelance", None, 0.6, True, None, None, None) for _ in range(3)],

  # --- Cluster 5: Cross-domain (10) ---
  *[("Customers who left bad reviews and got late deliveries",
     "SELECT cr.review_id FROM `{ds}.customer_reviews` cr JOIN `{ds}.marketplace_orders` mo ON cr.order_id=mo.order_id WHERE CAST(cr.review_score AS INT64)<=2 AND mo.order_delivered_customer_date>mo.order_estimated_delivery_date",
     ["customer_reviews","marketplace_orders"], "freelance", None, 0.55, True, None, None, None) for _ in range(4)],
  *[("Top customers and which DCs ship to them",
     None, ["users","order_items","inventory_items","distribution_centers"], "freelance", None, 0.45, False, "Complex multi-join; suggests graph traversal", None, None) for _ in range(3)],
  *[("Revenue impact of late deliveries",
     None, ["order_items","marketplace_orders"], "freelance", None, 0.4, False, "Cross-dataset join thelook<->Olist; schemas don't align", None, None) for _ in range(3)],
]

rows = []
for i, t in enumerate(CLUSTERS):
    q_text, sql, tables, path, agent, conf, success, err, thumbs, correction = t
    rows.append({
        "query_id": str(uuid.uuid4()),
        "user_id": random.choice(USERS),
        "question_text": q_text,
        "generated_sql": sql.format(ds=DS) if sql else None,
        "tables_referenced": tables,
        "path_taken": path,
        "agent_used": agent,
        "confidence_score": conf,
        "success": success,
        "error_message": err,
        "thumbs": thumbs,
        "correction": correction,
        "created_at": (NOW - timedelta(days=random.randint(0, 14), hours=random.randint(0, 23))).isoformat(),
    })

print(f"Inserting {len(rows)} query log rows...")
table = f"{PROJECT}.{DS}._flywheel_query_log"
errors = bq.insert_rows_json(table, rows)
if errors:
    print("ERRORS:", errors[:3])
else:
    print(f"OK. Inserted {len(rows)} rows into {table}")
