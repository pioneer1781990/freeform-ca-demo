"""Pre-cached answers for the demo. Mimics the exact CA API response format
captured from a real cymbal_sales_agent chat call.

Each entry returns a dict matching the shape of Answer fields:
narrative, sql, rows, agent_used, confidence, path_taken, citations,
thinking, latency_ms, studio_recommendations.

The orchestrator checks the cache first; on miss, falls through to the
real CA API + Claude fallback.
"""
from typing import Dict, Any, List, Optional
from core.output_contract import Answer, Citation


def _cit(kind, label, detail, **extra) -> Citation:
    return Citation(kind=kind, label=label, detail=detail, extra=extra)


# Key = normalized question text (lowercased, trimmed)
ANSWERS: Dict[str, Dict[str, Any]] = {

    # ------------------------------------------------------------
    # Beat 1 — Sales win
    # ------------------------------------------------------------
    "what was our revenue last month?": {
        "narrative": (
            "The total revenue for last month (April 2026) was **$405,498.47**. "
            "This calculation excludes orders that were cancelled or returned.\n\n"
            "### Insights\n"
            "- **Current Performance**: Monthly revenue has reached a strong level of approximately $405k.\n"
            "- **Data Integrity**: The result reflects successful transactions by filtering out non-revenue generating statuses like 'Cancelled' and 'Returned', as per standard business rules."
        ),
        "sql": (
            "SELECT SUM(order_items.sale_price) AS total_revenue\n"
            "FROM `new-project-495419.cymbal_retail.order_items` AS order_items\n"
            "WHERE order_items.created_at >= TIMESTAMP(DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 MONTH), MONTH))\n"
            "  AND order_items.created_at <  TIMESTAMP(DATE_TRUNC(CURRENT_DATE(), MONTH))\n"
            "  AND order_items.status NOT IN ('Cancelled', 'Returned')"
        ),
        "rows": [{"total_revenue": 405498.47}],
        "agent_used": "cymbal_sales_agent",
        "path_taken": "agent_route",
        "confidence": 0.95,
        "latency_ms": 1800,
        "tables_used": ["order_items"],
        "citations": [
            _cit("agent_rule", "Sales Analytics agent",
                 "Routed to this agent (covers orders, order_items, products, users)."),
            _cit("glossary", "Net Revenue",
                 "SUM(order_items.sale_price) excluding Cancelled and Returned items."),
            _cit("table", "order_items",
                 "`new-project-495419.cymbal_retail.order_items`"),
        ],
        "thinking": (
            "**Why this answer is trustworthy:**\n"
            "- Routed cleanly to the **Sales Analytics agent** (4 tables in scope: orders, order_items, products, users).\n"
            "- The agent's `Net Revenue` glossary rule (exclude Cancelled and Returned) was applied — no ambiguity.\n"
            "- Single-table aggregation over `order_items.sale_price`, filtered by status and date window."
        ),
    },

    # ------------------------------------------------------------
    # Beat 2 — CX agent answer driven by instruction + JOBS history
    # ------------------------------------------------------------
    "what's our late delivery rate by month?": {
        "narrative": (
            "Late delivery rate by month for the last 6 months, peaking in **April at 8.1%** "
            "and dropping to **6.4% in May**.\n\n"
            "### Insights\n"
            "- **Trend**: Late rate is improving since the April peak — likely tied to carrier negotiations.\n"
            "- **Instruction in play**: The CX agent's system instruction defines late as "
            "`order_delivered_customer_date > order_estimated_delivery_date`. Without that rule, "
            "different teams would arrive at different numbers (some count by carrier scan, others by "
            "promised vs delivered).\n"
            "- **Pattern Match**: `INFORMATION_SCHEMA.JOBS` shows this exact aggregation has been "
            "run **12 times** by analysts in the last 30 days — recognized as a verified query template."
        ),
        "sql": (
            "SELECT TIMESTAMP_TRUNC(order_purchase_timestamp, MONTH) AS month,\n"
            "       COUNTIF(order_delivered_customer_date > order_estimated_delivery_date) /\n"
            "         COUNTIF(order_delivered_customer_date IS NOT NULL) AS late_rate,\n"
            "       COUNT(*) AS orders\n"
            "FROM `new-project-495419.cymbal_retail.marketplace_orders`\n"
            "WHERE order_status = 'delivered'\n"
            "  AND order_purchase_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 180 DAY)\n"
            "GROUP BY month ORDER BY month"
        ),
        "rows": [
            {"month": "2025-12", "late_rate": 0.062, "orders":  8124},
            {"month": "2026-01", "late_rate": 0.071, "orders":  8842},
            {"month": "2026-02", "late_rate": 0.069, "orders":  8531},
            {"month": "2026-03", "late_rate": 0.077, "orders":  9018},
            {"month": "2026-04", "late_rate": 0.081, "orders":  9412},
            {"month": "2026-05", "late_rate": 0.064, "orders":  9106},
        ],
        "agent_used": "cymbal_customer_experience_agent",
        "path_taken": "agent_route",
        "confidence": 0.94,
        "latency_ms": 2100,
        "tables_used": ["marketplace_orders"],
        "citations": [
            _cit("agent_rule", "Customer Experience agent — late delivery rule",
                 "Agent system_instruction defines: late = order_delivered_customer_date > order_estimated_delivery_date. "
                 "This rule was applied to compute the rate consistently across months."),
            _cit("verified_query", "Late delivery rate by month",
                 "Recognized pattern from INFORMATION_SCHEMA.JOBS — run 12× by analysts in the last 30 days. "
                 "The CX agent picked this template as a verified query."),
            _cit("table", "marketplace_orders",
                 "`new-project-495419.cymbal_retail.marketplace_orders` — filtered to delivered orders."),
        ],
        "thinking": (
            "**Why this answer is trustworthy:**\n"
            "- Routed to the **Customer Experience agent** (review/delivery keywords).\n"
            "- The agent's system instruction encodes the late-delivery rule "
            "(`order_delivered_customer_date > order_estimated_delivery_date`) — "
            "so the metric is consistent across teams, not invented per question.\n"
            "- `INFORMATION_SCHEMA.JOBS` shows this exact aggregation pattern has been run **12 times** "
            "by analysts in the last 30 days. The CX agent treats it as a verified query template."
        ),
    },

    # ------------------------------------------------------------
    # Beat 3 — ambiguous term: present disambiguation options
    # ------------------------------------------------------------
    "what's our customer churn rate?": {
        "narrative": (
            "**Churn** means different things to different teams at Cymbal Retail. "
            "Before I run the numbers I want to make sure we agree on the definition. "
            "Pick one — I'll answer using that, and you can promote your choice to the "
            "Dataplex glossary so everyone gets the same number next time."
        ),
        "sql": None,
        "rows": None,
        "agent_used": None,
        "path_taken": "needs_disambiguation",
        "confidence": 0.0,
        "latency_ms": 900,
        "tables_used": [],
        "citations": [],
        "disambiguation_term": "churn",
        "options": [
            {"key": "90d",   "label": "No purchase in the last 90 days",
             "subtitle": "Most common across retail; balances churn signal with seasonal slack.",
             "definition": "A customer is churned if they have not placed a non-cancelled, non-returned order in the last 90 days."},
            {"key": "60d",   "label": "No purchase in the last 60 days (stricter)",
             "subtitle": "Catches churn earlier — useful for retention triggers.",
             "definition": "A customer is churned if they have not placed a non-cancelled, non-returned order in the last 60 days."},
            {"key": "1y",    "label": "No purchase in the last 12 months (loose)",
             "subtitle": "Reserved for low-frequency categories.",
             "definition": "A customer is churned if they have not placed an order in the last 12 months."},
            {"key": "single","label": "Never made a 2nd purchase",
             "subtitle": "Single-purchase customers, regardless of recency.",
             "definition": "A customer is churned if they have placed exactly one order, regardless of when."},
        ],
    },

    # Variant per option — same numbers shape, different narrative + cited definition
    "what's our customer churn rate? [post-choose-90d]": {
        "narrative": (
            "Using the **90-day rule** you selected, our customer churn rate is **38.4%**.\n\n"
            "### Insights\n"
            "- **Magnitude**: Roughly 4 in 10 customers fall into the churned bucket — material enough to warrant a retention campaign.\n"
            "- **Trend**: This is up 2.1pp from the same window last quarter — worth flagging.\n"
            "- **Definition sensitivity**: Tightening to 60 days would raise this to ~46%; loosening to 12 months drops it to ~22%."
        ),
        "thinking": (
            "**Why this answer is trustworthy now:**\n"
            "- You explicitly picked the 90-day definition, so the calculation is unambiguous.\n"
            "- The Sales agent applied your selection as if it were a glossary term for this session.\n"
            "- Once you promote this to Dataplex, the next person who asks the same question gets the same number "
            "without having to choose again."
        ),
        "sql": (
            "WITH last_order AS (\n"
            "  SELECT user_id, MAX(created_at) AS last_at\n"
            "  FROM `new-project-495419.cymbal_retail.order_items`\n"
            "  WHERE status NOT IN ('Cancelled','Returned')\n"
            "  GROUP BY 1\n"
            ")\n"
            "SELECT ROUND(COUNTIF(last_at < TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY)) / COUNT(*) * 100, 1) AS churn_pct\n"
            "FROM last_order"
        ),
        "rows": [{"churn_pct": 38.4}],
        "agent_used": "cymbal_sales_agent",
        "path_taken": "agent_route",
        "confidence": 0.95,
        "latency_ms": 1500,
        "tables_used": ["order_items"],
        "citations": [
            _cit("agent_rule", "Sales Analytics agent",
                 "Routed; using your selected churn definition for this answer."),
            _cit("memory", "Your selection: 90-day rule",
                 "A customer is churned if they have not placed a non-cancelled, non-returned order in the last 90 days."),
            _cit("table", "order_items",
                 "`new-project-495419.cymbal_retail.order_items`"),
        ],
        # Push a recommendation to Studio: promote the chosen definition.
        "studio_recommendations": [{
            "kind": "define_glossary_term",
            "term": "churn",
            "title": "Promote 'churn' (90-day rule) to Dataplex glossary",
            "evidence": "Siya picked the 90-day definition during a disambiguation. Promoting locks it in for everyone.",
            "draft_definition": "A customer is churned if they have not placed a non-cancelled, non-returned order in the last 90 days.",
        }],
    },

    "what's our customer churn rate? [post-choose-60d]": {
        "narrative": (
            "Using the **60-day rule** you selected, our customer churn rate is **45.7%**.\n\n"
            "### Insights\n"
            "- **Earlier signal**: 60 days catches churners ~30 days sooner than the 90-day rule — useful for win-back campaigns.\n"
            "- **Watch the noise**: 60-day windows are more sensitive to seasonal lulls; pair with category-level segmentation."
        ),
        "thinking": (
            "**Why this answer is trustworthy now:**\n"
            "- You explicitly picked the 60-day definition, so the calculation is unambiguous.\n"
            "- The Sales agent applied your selection as a temporary glossary term.\n"
            "- Promote this in Studio to lock it in for the rest of the team."
        ),
        "rows": [{"churn_pct": 45.7}],
        "agent_used": "cymbal_sales_agent",
        "path_taken": "agent_route",
        "confidence": 0.95,
        "latency_ms": 1500,
        "tables_used": ["order_items"],
        "citations": [
            _cit("agent_rule", "Sales Analytics agent",
                 "Routed; using your selected churn definition."),
            _cit("memory", "Your selection: 60-day rule",
                 "A customer is churned if they have not placed a non-cancelled, non-returned order in the last 60 days."),
            _cit("table", "order_items",
                 "`new-project-495419.cymbal_retail.order_items`"),
        ],
        "studio_recommendations": [{
            "kind": "define_glossary_term",
            "term": "churn",
            "title": "Promote 'churn' (60-day rule) to Dataplex glossary",
            "evidence": "Siya picked the 60-day definition during a disambiguation.",
            "draft_definition": "A customer is churned if they have not placed a non-cancelled, non-returned order in the last 60 days.",
        }],
    },

    "what's our customer churn rate? [post-choose-1y]": {
        "narrative": (
            "Using the **12-month rule** you selected, our customer churn rate is **22.1%**.\n\n"
            "### Insights\n"
            "- A looser window suits low-frequency categories (e.g., home goods).\n"
            "- For fashion/accessories, this likely under-counts true churn."
        ),
        "thinking": (
            "**Why this answer is trustworthy now:**\n"
            "- You explicitly picked the 12-month definition.\n"
            "- The agent applied your selection — no guessing on the window length.\n"
            "- Promote to share the choice with everyone else."
        ),
        "rows": [{"churn_pct": 22.1}],
        "agent_used": "cymbal_sales_agent",
        "path_taken": "agent_route",
        "confidence": 0.95,
        "latency_ms": 1500,
        "tables_used": ["order_items"],
        "citations": [
            _cit("agent_rule", "Sales Analytics agent", "Routed; applied 12-month rule."),
            _cit("memory", "Your selection: 12-month rule",
                 "A customer is churned if they have not placed an order in the last 12 months."),
            _cit("table", "order_items",
                 "`new-project-495419.cymbal_retail.order_items`"),
        ],
        "studio_recommendations": [{
            "kind": "define_glossary_term",
            "term": "churn",
            "title": "Promote 'churn' (12-month rule) to Dataplex glossary",
            "evidence": "Siya picked the 12-month definition during a disambiguation.",
            "draft_definition": "A customer is churned if they have not placed an order in the last 12 months.",
        }],
    },

    "what's our customer churn rate? [post-choose-single]": {
        "narrative": (
            "Using the **single-purchase rule** you selected, **51.3%** of our customers have churned by your definition.\n\n"
            "### Insights\n"
            "- This is a high number because most retailers have a long tail of one-time buyers.\n"
            "- Often paired with a 'never repeated' filter for acquisition-quality analysis."
        ),
        "thinking": (
            "**Why this answer is trustworthy now:**\n"
            "- You explicitly picked the single-purchase definition.\n"
            "- The agent treats one-time buyers as churned regardless of recency.\n"
            "- Promote to lock this definition in for the team."
        ),
        "rows": [{"churn_pct": 51.3}],
        "agent_used": "cymbal_sales_agent",
        "path_taken": "agent_route",
        "confidence": 0.95,
        "latency_ms": 1500,
        "tables_used": ["order_items"],
        "citations": [
            _cit("agent_rule", "Sales Analytics agent", "Routed; applied single-purchase rule."),
            _cit("memory", "Your selection: single-purchase rule",
                 "A customer is churned if they have placed exactly one order, regardless of when."),
            _cit("table", "order_items",
                 "`new-project-495419.cymbal_retail.order_items`"),
        ],
        "studio_recommendations": [{
            "kind": "define_glossary_term",
            "term": "churn",
            "title": "Promote 'churn' (single-purchase rule) to Dataplex glossary",
            "evidence": "Siya picked the single-purchase definition.",
            "draft_definition": "A customer is churned if they have placed exactly one order, regardless of when.",
        }],
    },

    # ------------------------------------------------------------
    # Beat 2c — partial CX answer with query-history fallback
    # ------------------------------------------------------------
    "average review score by brazilian state": {
        # The agent tried, failed silently on the join. Orchestrator fell back
        # to query-history pattern matching.
        "narrative": (
            "The Customer Experience agent couldn't directly answer this — "
            "it doesn't have a verified template for joining reviews to customer location.\n\n"
            "I found **3 historical analyst queries** that solved this by joining "
            "`customer_reviews → marketplace_orders → marketplace_customers`. "
            "Applying that pattern, the top 5 states by review score are below.\n\n"
            "**Confidence is 65%** because this is reconstructed from history, not from a verified rule. "
            "If you promote these patterns to the CX agent's verified queries, future answers will be instant and 95%."
        ),
        "sql": (
            "SELECT mc.customer_state AS state,\n"
            "       ROUND(AVG(CAST(cr.review_score AS INT64)), 2) AS avg_review,\n"
            "       COUNT(*) AS n\n"
            "FROM `new-project-495419.cymbal_retail.customer_reviews` cr\n"
            "JOIN `new-project-495419.cymbal_retail.marketplace_orders` mo ON cr.order_id = mo.order_id\n"
            "JOIN `new-project-495419.cymbal_retail.marketplace_customers` mc ON mo.customer_id = mc.customer_id\n"
            "GROUP BY 1 HAVING n > 100\n"
            "ORDER BY 2 DESC LIMIT 5"
        ),
        "rows": [
            {"state": "MG", "avg_review": 4.21, "n": 8431},
            {"state": "RS", "avg_review": 4.18, "n": 5912},
            {"state": "PR", "avg_review": 4.16, "n": 4878},
            {"state": "SP", "avg_review": 4.08, "n": 41202},
            {"state": "RJ", "avg_review": 3.94, "n": 12567},
        ],
        "agent_used": "cymbal_customer_experience_agent",
        "path_taken": "agent_route",
        "confidence": 0.65,
        "latency_ms": 2400,
        "tables_used": ["customer_reviews", "marketplace_orders", "marketplace_customers"],
        "citations": [
            _cit("agent_rule", "Customer Experience agent",
                 "Routed; agent had no verified template — orchestrator fell back to history."),
            _cit("verified_query", "3 historical patterns from query log",
                 "Analysts user_alice, user_dave, and user_grace solved this join in past sessions."),
            _cit("table", "customer_reviews", "`new-project-495419.cymbal_retail.customer_reviews`"),
            _cit("table", "marketplace_orders", "`new-project-495419.cymbal_retail.marketplace_orders`"),
            _cit("table", "marketplace_customers", "`new-project-495419.cymbal_retail.marketplace_customers`"),
        ],
        "studio_recommendations": [{
            "kind": "promote_verified_queries",
            "agent_id": "cymbal_customer_experience_agent",
            "title": "Promote 3 query-history patterns to CX agent",
            "evidence": "Question hedged because the CX agent lacked a verified template for this join. Three historical patterns from JOBS already solve it cleanly.",
            "patterns": [
                "Review score by customer state (Alice, May 12)",
                "Review distribution by city (Dave, May 8)",
                "CSAT by region with seller filter (Grace, May 14)",
            ],
        }],
        "thinking": (
            "**Why this answer should be treated cautiously:**\n"
            "- Routed to the **Customer Experience agent**, but its `example_queries` don't include this exact join.\n"
            "- I fell back to mining `INFORMATION_SCHEMA.JOBS` and found that 3 historical analyst queries solved this "
            "by joining `customer_reviews → marketplace_orders → marketplace_customers`. I applied that pattern.\n"
            "- Since this came from history rather than a verified rule, the result is reconstructed rather than authoritative. "
            "Promote the patterns in Studio so the agent learns them as verified queries."
        ),
    },

    "average review score by brazilian state [post-promote]": {
        "narrative": (
            "Top 5 Brazilian states by average review score:\n\n"
            "- **MG**: 4.21 across 8,431 reviews\n"
            "- **RS**: 4.18 across 5,912 reviews\n"
            "- **PR**: 4.16 across 4,878 reviews\n"
            "- **SP**: 4.08 across 41,202 reviews (highest volume)\n"
            "- **RJ**: 3.94 across 12,567 reviews\n\n"
            "### Insights\n"
            "- **South-Southeast Spread**: Southern states outperform; RJ is the only top-volume state with a sub-4 average.\n"
            "- **Volume vs Score**: SP dominates by volume but trails in score — a target for service-quality investigation."
        ),
        "sql": None,
        "rows": [
            {"state": "MG", "avg_review": 4.21, "n": 8431},
            {"state": "RS", "avg_review": 4.18, "n": 5912},
            {"state": "PR", "avg_review": 4.16, "n": 4878},
            {"state": "SP", "avg_review": 4.08, "n": 41202},
            {"state": "RJ", "avg_review": 3.94, "n": 12567},
        ],
        "agent_used": "cymbal_customer_experience_agent",
        "path_taken": "agent_route",
        "confidence": 0.95,
        "latency_ms": 1700,
        "tables_used": ["customer_reviews", "marketplace_orders", "marketplace_customers"],
        "citations": [
            _cit("agent_rule", "Customer Experience agent",
                 "Now answered via verified template (just promoted)."),
            _cit("verified_query", "Review score by customer state",
                 "Promoted from history to CX agent's example_queries.",
                 just_promoted=True),
            _cit("table", "customer_reviews", "`new-project-495419.cymbal_retail.customer_reviews`"),
        ],
        "thinking": (
            "**Why this answer is trustworthy now:**\n"
            "- The CX agent now has the customer-state join pattern in its `example_queries`.\n"
            "- This is the same data the previous answer derived from history — but now it's authoritative, "
            "because the agent owns the rule rather than reconstructing it each time."
        ),
    },

    # ------------------------------------------------------------
    # Beat 5 — Graph traversal
    # ------------------------------------------------------------
    "for our top 10 customers, which distribution centers stock the products they buy?": {
        "narrative": (
            "I attempted this as a 3-table join (`users → order_items → products → inventory_items`) "
            "but the result is brittle — each top customer appears tied to dozens of DCs because "
            "inventory_items contains stocking history rather than current allocation.\n\n"
            "This is a classic graph traversal question. **Adding `Customer → Product → DC` to the BQ Property Graph "
            "would let me answer this in one hop with 95% confidence.**"
        ),
        "sql": None,
        "rows": None,
        "agent_used": None,
        "path_taken": "freelance",
        "confidence": 0.40,
        "latency_ms": 2100,
        "tables_used": ["users", "order_items", "products", "inventory_items"],
        "citations": [
            _cit("table", "users + order_items + products + inventory_items",
                 "4-table join attempted; result not trustworthy without graph context."),
        ],
        "studio_recommendations": [{
            "kind": "add_graph_edge",
            "title": "Add edges to BQ Property Graph",
            "evidence": "3-table join needed; co-occurrence of users + products + inventory_items in 12 session queries.",
            "edges": ["Customer → Purchased → Product", "Product → StockedAt → DistributionCenter"],
        }],
        "thinking": (
            "**Why this answer is shaky:**\n"
            "- This is a classic multi-hop question: `users → order_items → products → inventory_items`.\n"
            "- I attempted a 4-table SQL join, but `inventory_items` represents historical stocking events, "
            "so each top customer appears linked to dozens of DCs — the result isn't what the question really asks.\n"
            "- Adding `Customer → Product → DC` edges to the property graph would let me answer this in **one traversal**. "
            "Studio is recommending exactly that."
        ),
    },

    "for our top 10 customers, which distribution centers stock the products they buy? [post-graph]": {
        "narrative": (
            "Using a graph traversal, here are the distribution centers that stock products bought by Cymbal Retail's top 10 customers by spend:\n\n"
            "- **Memphis TN**: stocks products bought by 9 of the top 10\n"
            "- **Chicago IL**: stocks products bought by 7 of the top 10\n"
            "- **Los Angeles CA**: stocks products bought by 6 of the top 10\n"
            "- **Mobile AL**: stocks products bought by 4 of the top 10\n\n"
            "### Insights\n"
            "- **Memphis is the gravity center** — fulfilling 9 of 10 top customers makes it the highest-leverage DC for top-customer retention.\n"
            "- This was a single graph traversal (`MATCH (c)-[:Purchased]->(p)-[:StockedAt]->(d)`) instead of a 4-way SQL join."
        ),
        "sql": (
            "SELECT d.name AS dc, COUNT(DISTINCT c.id) AS top_customers_served\n"
            "FROM GRAPH_TABLE(cymbal_retail.cymbal_retail_graph\n"
            "  MATCH (c:Customer)-[:Purchased]->(p:Product)-[:StockedAt]->(d:DistributionCenter)\n"
            "  WHERE c.id IN (SELECT user_id FROM top_customers_cte)\n"
            "  RETURN c.id AS cid, d.name AS name, d.id AS did)\n"
            "GROUP BY 1 ORDER BY 2 DESC LIMIT 10"
        ),
        "rows": [
            {"dc": "Memphis TN",     "top_customers_served": 9},
            {"dc": "Chicago IL",     "top_customers_served": 7},
            {"dc": "Los Angeles CA", "top_customers_served": 6},
            {"dc": "Mobile AL",      "top_customers_served": 4},
        ],
        "agent_used": "cymbal_sales_agent",
        "path_taken": "agent_route",
        "confidence": 0.95,
        "latency_ms": 1600,
        "tables_used": ["cymbal_retail_graph"],
        "citations": [
            _cit("agent_rule", "Sales Analytics agent",
                 "Routed; agent picked up the new graph edge."),
            _cit("table", "cymbal_retail_graph",
                 "BQ Property Graph (just enhanced with Customer→Product→DC edges).",
                 just_created=True),
        ],
        "thinking": (
            "**Why this answer is trustworthy now:**\n"
            "- The property graph now contains both `Customer → Purchased → Product` and `Product → StockedAt → DC` edges.\n"
            "- This becomes a single `MATCH (c)-[:Purchased]->(p)-[:StockedAt]->(d)` traversal instead of a 4-table join.\n"
            "- Same data underneath, but the graph structure expresses the intent of the question directly."
        ),
    },

    # ------------------------------------------------------------
    # Beat 6 — Unstructured / vector embeddings
    # ------------------------------------------------------------
    "what are customers most upset about in their reviews?": {
        "narrative": (
            "I scanned `review_comment_message` for keywords like 'bad', 'broken', 'late', 'wrong'. "
            "That returns 1,247 reviews — but it misses Portuguese phrases and any complaint that doesn't use those exact words.\n\n"
            "To answer this properly I'd need **semantic search over review text** — "
            "vector embeddings would let me cluster complaints by meaning rather than keyword."
        ),
        "sql": (
            "SELECT review_id, review_comment_message\n"
            "FROM `new-project-495419.cymbal_retail.customer_reviews`\n"
            "WHERE LOWER(review_comment_message) LIKE '%bad%'\n"
            "   OR LOWER(review_comment_message) LIKE '%broken%'\n"
            "   OR LOWER(review_comment_message) LIKE '%late%'\n"
            "   OR LOWER(review_comment_message) LIKE '%wrong%'\n"
            "LIMIT 1247"
        ),
        "rows": None,
        "agent_used": "cymbal_customer_experience_agent",
        "path_taken": "agent_route",
        "confidence": 0.45,
        "latency_ms": 2200,
        "tables_used": ["customer_reviews"],
        "citations": [
            _cit("agent_rule", "Customer Experience agent",
                 "Routed; keyword search returned shallow result."),
            _cit("table", "customer_reviews",
                 "`new-project-495419.cymbal_retail.customer_reviews` — text in Portuguese."),
        ],
        "studio_recommendations": [{
            "kind": "create_embeddings",
            "title": "Create vector embeddings on review_comment_message",
            "evidence": "Semantic question on free-text column; keyword search misses Portuguese and synonyms.",
            "target_table": "customer_reviews",
            "target_column": "review_comment_message",
        }],
        "thinking": (
            "**Why this answer is shallow:**\n"
            "- The free-text `review_comment_message` column is in Portuguese, and my only tool here is keyword `LIKE`.\n"
            "- I matched 1,247 reviews on a handful of English words — but I missed every complaint that used "
            "`atraso`, `danificado`, `quebrado`, `cor errada`, or any other Portuguese term.\n"
            "- This is a semantic question. It needs vector embeddings on the text column so similar complaints "
            "cluster regardless of exact wording. Studio is suggesting we build them."
        ),
    },

    "what are customers most upset about in their reviews? [post-embeddings]": {
        "narrative": (
            "Using vector search over the new review embeddings, the dissatisfaction themes are:\n\n"
            "1. **Late delivery** — 3,142 reviews cluster here (most cite `atraso` and `não chegou`)\n"
            "2. **Damaged packaging** — 1,876 reviews (`quebrado`, `amassado`, `embalagem ruim`)\n"
            "3. **Wrong item or color received** — 942 reviews (`cor errada`, `produto diferente`)\n"
            "4. **Missing items from multi-pack** — 408 reviews (`faltando`, `incompleto`)\n\n"
            "### Insights\n"
            "- **Delivery is the dominant pain point** — 3× more reviews than the next theme.\n"
            "- **Portuguese-language coverage is now captured** — keyword search would have missed all of these."
        ),
        "sql": (
            "WITH q AS (\n"
            "  SELECT ML.GENERATE_EMBEDDING(MODEL `cymbal_retail.gemini_text_embed`, 'reclamação cliente insatisfeito') AS query_emb\n"
            ")\n"
            "SELECT base.review_id, base.review_comment_message,\n"
            "       VECTOR_SEARCH(distance) AS similarity\n"
            "FROM VECTOR_SEARCH(\n"
            "  TABLE `cymbal_retail.review_embeddings`, 'embedding',\n"
            "  (SELECT query_emb FROM q), top_k => 5000)"
        ),
        "rows": [
            {"theme": "Late delivery (atraso/não chegou)",         "n_reviews": 3142},
            {"theme": "Damaged packaging (quebrado/amassado)",    "n_reviews": 1876},
            {"theme": "Wrong item or color (cor errada/diferente)","n_reviews":  942},
            {"theme": "Missing items (faltando/incompleto)",      "n_reviews":  408},
        ],
        "agent_used": "cymbal_customer_experience_agent",
        "path_taken": "agent_route",
        "confidence": 0.92,
        "latency_ms": 2400,
        "tables_used": ["review_embeddings", "customer_reviews"],
        "citations": [
            _cit("agent_rule", "Customer Experience agent",
                 "Routed; now using semantic search via vector index."),
            _cit("table", "review_embeddings",
                 "Vector index over review_comment_message (just created).",
                 just_created=True),
        ],
        "thinking": (
            "**Why this answer is trustworthy now:**\n"
            "- The CX agent now calls `VECTOR_SEARCH` over the new `review_embeddings` table.\n"
            "- Embeddings capture meaning rather than exact words, so `atraso`, `não chegou`, `demorou demais` "
            "all cluster as 'late delivery' even though they share no keywords.\n"
            "- Themes are derived from semantic similarity — language-agnostic."
        ),
    },

    # ------------------------------------------------------------
    # Inheritance variants — non-Siya users ask the same question
    # Siya already enriched. The system inherits the rule; the user
    # didn't have to define anything.
    # ------------------------------------------------------------
    "what's our customer churn rate? [inherited-by-alex-from-churn-defined]": {
        "narrative": (
            "Using the 'churn' definition added by Siya last session — customer with no order in 90 days — "
            "our customer churn rate is **38.4%**. "
            "You didn't have to define anything; the Sales agent inherited the glossary term automatically. "
            "Next quarter, anyone on the team asking this gets the same number, instantly."
        ),
        "sql": (
            "WITH last_order AS (\n"
            "  SELECT user_id, MAX(created_at) AS last_at\n"
            "  FROM `new-project-495419.cymbal_retail.order_items`\n"
            "  WHERE status NOT IN ('Cancelled','Returned')\n"
            "  GROUP BY 1\n"
            ")\n"
            "SELECT ROUND(COUNTIF(last_at < TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY)) / COUNT(*) * 100, 1) AS churn_pct\n"
            "FROM last_order"
        ),
        "rows": [{"churn_pct": 38.4}],
        "agent_used": "cymbal_sales_agent",
        "path_taken": "agent_route",
        "confidence": 0.95,
        "latency_ms": 1500,
        "tables_used": ["order_items"],
        "citations": [
            _cit("agent_rule", "Sales Analytics agent",
                 "Routed; applied the inherited churn glossary term — no disambiguation needed."),
            _cit("glossary", "🧠 Inherited: glossary term 'churn' defined by Siya, May 20",
                 "A customer is churned if they have not placed a non-cancelled, non-returned order in the last 90 days. "
                 "Promoted to the Dataplex glossary by Siya — Alex inherits it automatically.",
                 inherited=True),
            _cit("table", "order_items",
                 "`new-project-495419.cymbal_retail.order_items`"),
        ],
        "thinking": (
            "**Why this answer is instant for Alex:**\n"
            "- Siya promoted the 90-day churn definition to the Dataplex glossary in her last session.\n"
            "- The Sales agent picks up the glossary term automatically — Alex never sees the disambiguation prompt.\n"
            "- Same calculation, same number, no extra work — inheritance is the point."
        ),
    },

    "average review score by brazilian state [inherited-by-alex-from-cx-verified-queries]": {
        "narrative": (
            "Top 5 Brazilian states by average review score — answered directly via the CX agent's verified queries "
            "(promoted by Siya last session). You didn't have to dig through query history; the agent already owns the join "
            "pattern. **MG** leads at 4.21, followed by RS (4.18) and PR (4.16); SP carries the volume at 41,202 reviews."
        ),
        "sql": None,
        "rows": [
            {"state": "MG", "avg_review": 4.21, "n": 8431},
            {"state": "RS", "avg_review": 4.18, "n": 5912},
            {"state": "PR", "avg_review": 4.16, "n": 4878},
            {"state": "SP", "avg_review": 4.08, "n": 41202},
            {"state": "RJ", "avg_review": 3.94, "n": 12567},
        ],
        "agent_used": "cymbal_customer_experience_agent",
        "path_taken": "agent_route",
        "confidence": 0.95,
        "latency_ms": 1500,
        "tables_used": ["customer_reviews", "marketplace_orders", "marketplace_customers"],
        "citations": [
            _cit("agent_rule", "Customer Experience agent",
                 "Routed; the inherited verified template handled the 3-table join directly."),
            _cit("verified_query", "✅ Inherited: 3 verified queries on CX agent (promoted by Siya, May 20)",
                 "Review-by-state, review-by-city, and CSAT-by-region patterns were promoted from query history "
                 "to the CX agent's example_queries by Siya. Alex inherits them automatically.",
                 inherited=True),
            _cit("table", "customer_reviews", "`new-project-495419.cymbal_retail.customer_reviews`"),
        ],
        "thinking": (
            "**Why this answer is instant for Alex:**\n"
            "- Siya promoted three historical patterns to the CX agent's verified queries last session.\n"
            "- The agent now answers this join with 95% confidence directly — no fallback to query history.\n"
            "- The system inherited the rule; Alex did zero promotion work."
        ),
    },

    "for our top 10 customers, which distribution centers stock the products they buy? [inherited-by-alex-from-graph-extended]": {
        "narrative": (
            "Answered via a single graph traversal — `Customer → Purchased → Product → StockedAt → DC` — using the edges "
            "Siya added to the BQ Property Graph last session. **Memphis TN** stocks products for 9 of the top 10, "
            "**Chicago IL** for 7, **Los Angeles CA** for 6, and **Mobile AL** for 4. "
            "You didn't have to define the graph relationships; the system inherited them."
        ),
        "sql": (
            "SELECT d.name AS dc, COUNT(DISTINCT c.id) AS top_customers_served\n"
            "FROM GRAPH_TABLE(cymbal_retail.cymbal_retail_graph\n"
            "  MATCH (c:Customer)-[:Purchased]->(p:Product)-[:StockedAt]->(d:DistributionCenter)\n"
            "  WHERE c.id IN (SELECT user_id FROM top_customers_cte)\n"
            "  RETURN c.id AS cid, d.name AS name, d.id AS did)\n"
            "GROUP BY 1 ORDER BY 2 DESC LIMIT 10"
        ),
        "rows": [
            {"dc": "Memphis TN",     "top_customers_served": 9},
            {"dc": "Chicago IL",     "top_customers_served": 7},
            {"dc": "Los Angeles CA", "top_customers_served": 6},
            {"dc": "Mobile AL",      "top_customers_served": 4},
        ],
        "agent_used": "cymbal_sales_agent",
        "path_taken": "agent_route",
        "confidence": 0.95,
        "latency_ms": 1500,
        "tables_used": ["cymbal_retail_graph"],
        "citations": [
            _cit("agent_rule", "Sales Analytics agent",
                 "Routed; the inherited graph edges turned a 4-table join into a single traversal."),
            _cit("table", "📊 Inherited: BQ Property Graph (DC edges added by Siya, May 20)",
                 "`Customer → Purchased → Product` and `Product → StockedAt → DistributionCenter` "
                 "edges were added to the property graph by Siya. Alex inherits the structure automatically.",
                 inherited=True),
        ],
        "thinking": (
            "**Why this answer is instant for Alex:**\n"
            "- Siya added the `Purchased` and `StockedAt` edges to the BQ Property Graph last session.\n"
            "- The Sales agent now resolves the question in one traversal — no brittle 4-table join.\n"
            "- The graph structure was inherited; Alex didn't have to touch the schema."
        ),
    },

    "what are customers most upset about in their reviews? [inherited-by-alex-from-embeddings-created]": {
        "narrative": (
            "Using vector search over the `review_embeddings` index built by Siya last session, dissatisfaction clusters as: "
            "**Late delivery** (3,142 reviews — `atraso`, `não chegou`), **Damaged packaging** (1,876 — `quebrado`, `amassado`), "
            "**Wrong item or color** (942 — `cor errada`), and **Missing items** (408 — `faltando`). "
            "You didn't have to build the index — the system inherited the semantic layer Siya created."
        ),
        "sql": (
            "WITH q AS (\n"
            "  SELECT ML.GENERATE_EMBEDDING(MODEL `cymbal_retail.gemini_text_embed`, 'reclamação cliente insatisfeito') AS query_emb\n"
            ")\n"
            "SELECT base.review_id, base.review_comment_message,\n"
            "       VECTOR_SEARCH(distance) AS similarity\n"
            "FROM VECTOR_SEARCH(\n"
            "  TABLE `cymbal_retail.review_embeddings`, 'embedding',\n"
            "  (SELECT query_emb FROM q), top_k => 5000)"
        ),
        "rows": [
            {"theme": "Late delivery (atraso/não chegou)",         "n_reviews": 3142},
            {"theme": "Damaged packaging (quebrado/amassado)",    "n_reviews": 1876},
            {"theme": "Wrong item or color (cor errada/diferente)","n_reviews":  942},
            {"theme": "Missing items (faltando/incompleto)",      "n_reviews":  408},
        ],
        "agent_used": "cymbal_customer_experience_agent",
        "path_taken": "agent_route",
        "confidence": 0.92,
        "latency_ms": 1500,
        "tables_used": ["review_embeddings", "customer_reviews"],
        "citations": [
            _cit("agent_rule", "Customer Experience agent",
                 "Routed; semantic search resolved the question without keyword fallback."),
            _cit("table", "🧠 Inherited: review_embeddings vector index (built by Siya, May 20)",
                 "Vector embeddings over `review_comment_message` were built by Siya. "
                 "Alex inherits the index — `VECTOR_SEARCH` works immediately, no setup required.",
                 inherited=True),
        ],
        "thinking": (
            "**Why this answer is instant for Alex:**\n"
            "- Siya created the `review_embeddings` vector index last session.\n"
            "- The CX agent now calls `VECTOR_SEARCH` directly — Portuguese clusters with English by meaning.\n"
            "- The embedding pipeline was inherited; Alex didn't have to provision anything."
        ),
    },
}


def _normalize(q: str) -> str:
    return " ".join(q.lower().strip().rstrip("?.!").split())


# Loose-match aliases — common phrasings the demo audience might type that
# should still hit the cached demo answers. Keys are normalized aliases,
# values are the canonical cache key.
_ALIASES: Dict[str, str] = {
    # Beat 1 — revenue
    "revenue last month":                       "what was our revenue last month",
    "what was the revenue last month":          "what was our revenue last month",
    "monthly revenue":                          "what was our revenue last month",
    # Beat 2 — late delivery
    "what is our late delivery rate":           "what's our late delivery rate by month",
    "what's our late delivery rate":            "what's our late delivery rate by month",
    "what's our late delivery rate this month": "what's our late delivery rate by month",
    "late delivery rate":                       "what's our late delivery rate by month",
    "late deliveries":                          "what's our late delivery rate by month",
    # Beat 3 — churn
    "what is our customer churn rate":          "what's our customer churn rate",
    "churn rate":                               "what's our customer churn rate",
    "customer churn":                           "what's our customer churn rate",
    # Beat 4 — review by state
    "review score by state":                    "average review score by brazilian state",
    "review by state":                          "average review score by brazilian state",
    "average review score by state":            "average review score by brazilian state",
    # Beat 5 — graph multi-hop
    "top customers and distribution centers":   "for our top 10 customers, which distribution centers stock the products they buy",
    "which dcs ship to our top customers":      "for our top 10 customers, which distribution centers stock the products they buy",
    "top customers dcs":                        "for our top 10 customers, which distribution centers stock the products they buy",
    # Beat 6 — semantic complaints
    "what are customers upset about":           "what are customers most upset about in their reviews",
    "customer complaints":                      "what are customers most upset about in their reviews",
    "what do customers complain about":         "what are customers most upset about in their reviews",
    "common complaints":                        "what are customers most upset about in their reviews",
}


_ANSWERS_NORM: Dict[str, Dict[str, Any]] = {_normalize(k): v for k, v in ANSWERS.items()}


def lookup(question: str, suffix: str = "") -> Optional[Dict[str, Any]]:
    """Return cached answer if available; None otherwise.

    Tries exact normalized match first, then a small alias map so common
    phrasing variants still hit the demo cache.

    `suffix` lets us key into post-action variants (e.g. "[post-choose-90d]")."""
    norm = _normalize(question)
    canon = _ALIASES.get(norm, norm)
    suffix_norm = _normalize(suffix) if suffix else ""
    key = canon + (f" {suffix_norm}" if suffix_norm else "")
    hit = _ANSWERS_NORM.get(key)
    if hit: return hit
    # Fallback to literal lookup (preserves backward compat)
    return ANSWERS.get(question.lower().strip() + (f" {suffix}" if suffix else ""))


def to_answer(question: str, cached: Dict[str, Any]) -> Answer:
    """Convert cache dict to the Answer dataclass the orchestrator returns."""
    return Answer(
        question=question,
        path_taken=cached.get("path_taken", "agent_route"),
        narrative=cached.get("narrative", ""),
        sql=cached.get("sql"),
        rows=cached.get("rows"),
        row_count=len(cached.get("rows") or []),
        columns=list(cached["rows"][0].keys()) if cached.get("rows") else None,
        confidence=cached.get("confidence", 0.0),
        agent_used=cached.get("agent_used"),
        citations=cached.get("citations", []),
        tables_used=cached.get("tables_used", []),
        thinking=cached.get("thinking"),
        latency_ms=cached.get("latency_ms", 0),
    )
