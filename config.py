"""Central config — all module paths import from here."""
import os

PROJECT_ID     = os.environ.get("PROJECT_ID", "new-project-495419")
PROJECT_NUMBER = "802175491358"
DATASET        = os.environ.get("DATASET", "cymbal_retail")
BQ_LOCATION    = os.environ.get("BQ_LOCATION", "US")
GCS_BUCKET     = os.environ.get("GCS_BUCKET", "new-project-495419-cymbal-retail")
CONNECTION_ID  = "us.cymbal-gcs-conn"

FQDS = f"`{PROJECT_ID}.{DATASET}`"
def t(name: str) -> str:
    return f"`{PROJECT_ID}.{DATASET}.{name}`"

CA_LOCATION   = "global"
GEMINI_MODEL  = "gemini-2.5-flash"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL  = "claude-sonnet-4-5-20250929"  # fallback when CA API unavailable

PRECREATED_AGENT_ID = "cymbal_sales_agent"

PROD_TABLES = [
    "orders","order_items","products","users",
    "customer_reviews","customer_payments","marketplace_orders",
    "marketplace_customers","marketplace_sellers",
    "distribution_centers","inventory_items","inventory_snapshots","supplier_catalog",
    "support_tickets","return_claims",
    "review_docs","support_ticket_docs","return_evidence_docs","product_images",
]
DEV_TABLES = ["orders_staging","products_dev","user_events_raw","tmp_analysis_20260510"]
