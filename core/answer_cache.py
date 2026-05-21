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
        "thinking": "Analyzing context\nRetrieved context for 4 tables.\nRunning a query: revenue last month",
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
    },

    # ------------------------------------------------------------
    # Beat 2b — undefined term: customer churn
    # ------------------------------------------------------------
    "what's our customer churn rate?": {
        "narrative": (
            "I made an assumption here: I treated **churn** as a customer with no purchases in the last 90 days who had at least one prior order. "
            "Under that definition, the churn rate is approximately **38.4%**.\n\n"
            "### Caveat\n"
            "Different teams define churn differently — 60 vs 90 days, or based on last contact vs last purchase. "
            "I'm only **50% confident** until a definition is added to the glossary."
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
        "confidence": 0.50,
        "latency_ms": 1600,
        "tables_used": ["order_items"],
        "citations": [
            _cit("agent_rule", "Sales Analytics agent",
                 "Routed; agent has no glossary entry for 'churn'."),
            _cit("table", "order_items",
                 "`new-project-495419.cymbal_retail.order_items`"),
        ],
        # Studio reaction
        "studio_recommendations": [{
            "kind": "define_glossary_term",
            "term": "churn",
            "title": "Define 'churn' in the glossary",
            "evidence": "Question answered with a 50% confidence hedge because 'churn' has no definition.",
            "draft_definition": "A customer who placed an order more than 90 days ago and has not ordered since.",
        }],
    },

    # After definition is added, re-ask works confidently
    "what's our customer churn rate? [post-define]": {
        "narrative": (
            "Our customer churn rate is **38.4%**, using the definition you just added: "
            "*a customer with no purchases in the last 90 days who had at least one prior order*.\n\n"
            "### Insights\n"
            "- **Magnitude**: Roughly 4 in 10 customers fall into the churned bucket — material enough to warrant a retention campaign.\n"
            "- **Definition Sensitivity**: Tightening to 60 days raises this number; consider tracking both."
        ),
        "sql": None,  # same SQL as above
        "rows": [{"churn_pct": 38.4}],
        "agent_used": "cymbal_sales_agent",
        "path_taken": "agent_route",
        "confidence": 0.95,
        "latency_ms": 1500,
        "tables_used": ["order_items"],
        "citations": [
            _cit("agent_rule", "Sales Analytics agent", "Same routing as before."),
            _cit("glossary", "churn", "A customer who placed an order more than 90 days ago and has not ordered since.",
                 just_defined=True),
            _cit("table", "order_items",
                 "`new-project-495419.cymbal_retail.order_items`"),
        ],
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
            "evidence": "Question hedged at 65% because the CX agent lacked a verified template for this join. Three historical patterns from JOBS already solve it cleanly.",
            "patterns": [
                "Review score by customer state (Alice, May 12)",
                "Review distribution by city (Dave, May 8)",
                "CSAT by region with seller filter (Grace, May 14)",
            ],
        }],
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
    },
}


def _normalize(q: str) -> str:
    return " ".join(q.lower().strip().split())


def lookup(question: str, suffix: str = "") -> Optional[Dict[str, Any]]:
    """Return cached answer if available; None otherwise.

    `suffix` lets us key into post-action variants (e.g. "[post-define]")."""
    key = _normalize(question) + (f" {suffix}" if suffix else "")
    return ANSWERS.get(key)


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
